import os
import shutil
import zipfile
import uuid
from datetime import datetime
from typing import List, Dict, Any, Tuple
import yaml
import sqlite3

from modules.storage_service import StorageServiceInterface
from modules.email_service import EmailWorker
from modules.offer_generator import OfferGenerator
from modules.report_service import ReportService
from modules.pdf_service import PdfService
from modules.logger_service import log_service
from modules.models import CampaignData, GenerationResult, EmailResult
from modules.constants import GENERATED_DIR, DOCUMENT_TYPES_CONFIG

class CampaignManager:
    def __init__(self, 
                 storage_service: StorageServiceInterface, 
                 email_worker: EmailWorker, 
                 offer_generator: OfferGenerator,
                 report_service: ReportService):
        self.storage = storage_service
        self.email_worker = email_worker
        self.offer_generator = offer_generator
        self.report_service = report_service
        
        # Load document types config
        with open(DOCUMENT_TYPES_CONFIG, "r") as f:
            self.doc_types = yaml.safe_load(f).get("document_types", {})

    def _get_campaign_dir(self, campaign_name: str) -> str:
        safe_name = campaign_name.replace(" ", "_")
        return os.path.join(GENERATED_DIR, safe_name)

    def create_campaign_record(self, name: str, doc_type_key: str, client: str, subject: str, body_template: str, template_version: str) -> CampaignData:
        campaign = CampaignData(
            id=str(uuid.uuid4()),
            name=name,
            doc_type=doc_type_key,
            client=client,
            subject=subject,
            body_template=body_template,
            template_version=template_version,
            status="Draft",
            created_at=datetime.now()
        )
        self.storage.create_campaign(campaign)
        log_service.info("CampaignManager", f"Created campaign record: {name}", campaign.id)
        return campaign

    def run_generation(self, campaign: CampaignData, template_path: str, candidates: List[Dict[str, Any]]) -> GenerationResult:
        campaign_dir = self._get_campaign_dir(campaign.name)
        log_service.set_campaign_log(campaign_dir)
        
        doc_config = self.doc_types.get(campaign.doc_type, {})
        prefix = doc_config.get("prefix", "NAV")
        
        log_service.info("CampaignManager", f"Starting generation for {len(candidates)} candidates", campaign.id)
        
        self.storage.update_campaign_status(campaign.id, "Generating")
        
        result, documents = self.offer_generator.generate_documents(
            campaign_dir=campaign_dir,
            campaign_id=campaign.id,
            prefix=prefix,
            client_code=campaign.client,
            template_path=template_path,
            candidates=candidates
        )
        
        # Save to DB transactionally
        success = self.storage.save_documents_and_queue_transaction(campaign.id, documents)
        if not success:
            log_service.error("CampaignManager", "Failed to save generated documents to database.", campaign.id)
            self.storage.update_campaign_status(campaign.id, "Failed")
            result.success = False
            return result
            
        self.storage.update_campaign_status(campaign.id, "Generated")
        return result

    def start_email_campaign(self, campaign: CampaignData, should_stop: callable) -> EmailResult:
        self.storage.update_campaign_status(campaign.id, "Sending")
        log_service.info("CampaignManager", f"Starting email sending for {campaign.name}", campaign.id)
        
        result = self.email_worker.process_queue(campaign, should_stop)
        
        if not should_stop():
            self.storage.update_campaign_status(campaign.id, "Completed")
            self.report_service.generate_reports(campaign, self._get_campaign_dir(campaign.name))
            self.generate_zip(campaign)
            
        return result

    def generate_zip(self, campaign: CampaignData):
        campaign_dir = self._get_campaign_dir(campaign.name)
        zip_dir = os.path.join(campaign_dir, "zip")
        os.makedirs(zip_dir, exist_ok=True)
        
        zip_path = os.path.join(zip_dir, f"{campaign.name}.zip")
        pdf_dir = os.path.join(campaign_dir, "pdf")
        
        if os.path.exists(pdf_dir):
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(pdf_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, pdf_dir)
                        zipf.write(file_path, arcname)
                        
            log_service.info("CampaignManager", f"Generated ZIP archive at {zip_path}", campaign.id)
            return zip_path
        return None

    def get_interrupted_campaign(self) -> Optional[CampaignData]:
        # Check DB for campaigns in 'Sending' status (or generating)
        with self.storage.get_connection() as conn:
            conn.row_factory = sqlite3.Row if hasattr(sqlite3, 'Row') else None
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM campaigns WHERE status IN ('Sending', 'Generating')")
            row = cursor.fetchone()
            if row:
                return CampaignData(
                    id=row[0], name=row[1], doc_type=row[2], client=row[3], subject=row[4],
                    body_template=row[5], template_version=row[6], status=row[7],
                    created_at=row[8], completed_at=row[9]
                )
        return None
