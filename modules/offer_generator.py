import os
import time
from typing import List, Dict, Any
from modules.models import GenerationResult, DocumentData
from modules.template_engine import TemplateEngine
from modules.pdf_service import PdfService
from modules.logger_service import log_service
import uuid

class OfferGenerator:
    def __init__(self, pdf_service: PdfService):
        self.pdf_service = pdf_service

    def generate_sequence_number(self, prefix: str, client_code: str, year: str, sequence: int) -> str:
        """Generates NAV-ATL-2026-0001 style string."""
        return f"{prefix}-{client_code}-{year}-{sequence:04d}"

    def generate_documents(self, 
                           campaign_dir: str, 
                           campaign_id: str,
                           prefix: str,
                           client_code: str,
                           template_path: str,
                           candidates: List[Dict[str, Any]]) -> GenerationResult:
        """
        Generates Word documents and PDFs for a list of candidates.
        Returns GenerationResult.
        """
        start_time = time.time()
        generated = 0
        failed = 0
        warnings = []
        errors = []
        
        docx_dir = os.path.join(campaign_dir, "docx")
        pdf_dir = os.path.join(campaign_dir, "pdf")
        os.makedirs(docx_dir, exist_ok=True)
        os.makedirs(pdf_dir, exist_ok=True)
        
        year = str(time.localtime().tm_year)
        
        documents = []

        for index, candidate in enumerate(candidates, start=1):
            try:
                # Generate unique sequence
                seq_num = self.generate_sequence_number(prefix, client_code, year, index)
                candidate["doc_number"] = seq_num
                
                # File names
                first_name = candidate.get('candidate_name', 'Unknown').replace(" ", "_")
                base_name = f"{seq_num}_{first_name}"
                docx_path = os.path.join(docx_dir, f"{base_name}.docx")
                pdf_path = os.path.join(pdf_dir, f"{base_name}.pdf")
                
                # Generate Docx
                TemplateEngine.render_docx(template_path, docx_path, candidate)
                
                # Convert to PDF
                success = self.pdf_service.convert_to_pdf(docx_path, pdf_path)
                if not success:
                    raise Exception(f"PDF conversion failed for {base_name}")
                
                documents.append(DocumentData(
                    id=str(uuid.uuid4()),
                    campaign_id=campaign_id,
                    doc_number=seq_num,
                    candidate_name=candidate.get('candidate_name', ''),
                    email=candidate.get('email', ''),
                    pdf_path=pdf_path,
                    docx_path=docx_path,
                    status="Generated",
                    variables=candidate
                ))
                generated += 1
                
            except Exception as e:
                failed += 1
                errors.append(f"Failed generating for {candidate.get('email', 'Unknown')}: {str(e)}")
                log_service.error("OfferGenerator", f"Failed generating for {candidate.get('email', 'Unknown')}: {str(e)}", campaign_id)

        duration = time.time() - start_time
        
        return GenerationResult(
            success=(failed == 0),
            generated=generated,
            failed=failed,
            duration_secs=duration,
            warnings=warnings,
            errors=errors
        ), documents
