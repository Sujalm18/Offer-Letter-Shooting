import os
import subprocess
from modules.logger_service import log_service

class PdfService:
    def __init__(self):
        self.word_installed = self._check_word_installed()
        self.libreoffice_installed = self._check_libreoffice_installed()
        
    def _check_word_installed(self) -> bool:
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Quit()
            return True
        except Exception:
            return False

    def _check_libreoffice_installed(self) -> bool:
        # Check standard installation paths for LibreOffice on Windows and Linux
        paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            "/usr/bin/soffice"
        ]
        for path in paths:
            if os.path.exists(path):
                self.libreoffice_path = path
                return True
        return False

    def convert_to_pdf(self, docx_path: str, pdf_path: str) -> bool:
        if self.word_installed:
            try:
                from docx2pdf import convert
                convert(docx_path, pdf_path)
                return True
            except Exception as e:
                log_service.error("PdfService", f"docx2pdf failed for {docx_path}: {e}")
                
        if self.libreoffice_installed:
            try:
                output_dir = os.path.dirname(pdf_path)
                # soffice --headless --convert-to pdf "file.docx" --outdir "output_dir"
                subprocess.run([
                    self.libreoffice_path,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    docx_path,
                    "--outdir",
                    output_dir
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # LibreOffice outputs the file with the same name but .pdf extension in the outdir
                expected_pdf_name = os.path.basename(docx_path).replace(".docx", ".pdf")
                expected_pdf_path = os.path.join(output_dir, expected_pdf_name)
                
                # If the requested pdf_path is different, rename it
                if os.path.abspath(expected_pdf_path) != os.path.abspath(pdf_path):
                    if os.path.exists(expected_pdf_path):
                        os.replace(expected_pdf_path, pdf_path)
                return True
            except Exception as e:
                log_service.error("PdfService", f"LibreOffice failed for {docx_path}: {e}")
                
        log_service.error("PdfService", "No PDF conversion engine available or both failed.")
        return False
