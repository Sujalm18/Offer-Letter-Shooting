import os
import json
import csv
import sqlite3
from typing import Dict, Any, List
from modules.models import CampaignData
from modules.storage_service import StorageServiceInterface
from modules.logger_service import log_service

class ReportService:
    def __init__(self, storage_service: StorageServiceInterface):
        self.storage = storage_service

    def generate_reports(self, campaign: CampaignData, campaign_dir: str):
        reports_dir = os.path.join(campaign_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Get all queue data for this campaign
        queue_data = self.storage.get_pending_queue(campaign.id)
        # Actually we need all data, not just pending
        # Let's write a quick query to get all docs and queue status
        with self.storage.get_connection() as conn:
            conn.row_factory = sqlite3.Row if hasattr(sqlite3, 'Row') else None # It's imported in storage_service, we'll just do a raw query here
            cursor = conn.cursor()
            cursor.execute('''
                SELECT d.candidate_name, d.email, q.status, q.error_msg
                FROM documents d
                LEFT JOIN email_queue q ON d.id = q.doc_id
                WHERE d.campaign_id = ?
            ''', (campaign.id,))
            
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        sent = [r for r in results if r['status'] == 'Sent']
        failed = [r for r in results if r['status'] == 'Failed']
        
        # Campaign.json
        summary = {
            "campaign": campaign.name,
            "client": campaign.client,
            "subject": campaign.subject,
            "template_version": campaign.template_version,
            "total_candidates": len(results),
            "generated": len(results), # Assuming all generated for now
            "sent": len(sent),
            "failed": len(failed),
            "duration": str(campaign.completed_at - campaign.created_at) if campaign.completed_at else "In Progress"
        }
        
        with open(os.path.join(reports_dir, "campaign.json"), "w") as f:
            json.dump(summary, f, indent=4)
            
        # CSVs
        self._write_csv(os.path.join(reports_dir, "Campaign.csv"), results, ["candidate_name", "email", "status", "error_msg"])
        self._write_csv(os.path.join(reports_dir, "Sent.csv"), sent, ["candidate_name", "email"])
        self._write_csv(os.path.join(reports_dir, "Failed.csv"), failed, ["candidate_name", "email", "error_msg"])
        
        log_service.info("ReportService", f"Reports generated at {reports_dir}", campaign.id)
        return summary
        
    def _write_csv(self, filepath: str, data: List[Dict], fieldnames: List[str]):
        if not data:
            return
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
