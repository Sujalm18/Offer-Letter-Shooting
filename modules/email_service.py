import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import time
import json
from typing import Optional
from modules.models import EmailResult, CampaignData
from modules.storage_service import StorageServiceInterface
from modules.template_engine import TemplateEngine
from modules.logger_service import log_service
from modules.constants import QueueState
from config import config

class EmailWorker:
    def __init__(self, storage_service: StorageServiceInterface):
        self.storage = storage_service
        self.server: Optional[smtplib.SMTP] = None

    def reconnect_server(self):
        try:
            if self.server:
                try:
                    self.server.quit()
                except:
                    pass
            self.server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=30)
            self.server.ehlo()
            self.server.starttls(context=ssl.create_default_context())
            self.server.ehlo()
            self.server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
            return True
        except Exception as e:
            log_service.error("EmailWorker", f"Failed to connect to SMTP: {str(e)}")
            return False

    def send_single_email(self, 
                          to_email: str, 
                          subject: str, 
                          body_html: str, 
                          attachment_path: Optional[str] = None) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = config.SMTP_EMAIL
            msg["To"] = to_email
            msg["Subject"] = subject
            
            msg.attach(MIMEText(body_html, "html"))
            
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                    msg.attach(part)
                    
            self.server.sendmail(config.SMTP_EMAIL, to_email, msg.as_string())
            return True
        except Exception as e:
            log_service.error("EmailWorker", f"Failed sending email to {to_email}: {str(e)}")
            return False

    def process_queue(self, campaign: CampaignData, should_stop: callable = lambda: False) -> EmailResult:
        """
        Processes the email queue for a specific campaign.
        Runs until the queue is empty or should_stop() returns True.
        """
        start_time = time.time()
        sent = 0
        failed = 0
        
        if not self.reconnect_server():
            return EmailResult(False, 0, 0, 0.0, ["Failed to connect to SMTP server."])

        queue = self.storage.get_pending_queue(campaign.id)
        if not queue:
            return EmailResult(True, 0, 0, 0.0, [])
            
        successful_sends_since_reconnect = 0
        
        for item in queue:
            if should_stop():
                log_service.info("EmailWorker", f"Queue processing paused for campaign {campaign.name}", campaign.id)
                break
                
            doc_id = item["doc_id"]
            to_email = item["email"]
            pdf_path = item["pdf_path"]
            variables = json.loads(item.get("variables", "{}"))
            
            self.storage.update_queue_status(doc_id, QueueState.SENDING)
            
            # Render body
            body_html = TemplateEngine.render_email_body(campaign.body_template, variables)
            
            success = False
            for attempt in range(1, config.RETRY_COUNT + 1):
                success = self.send_single_email(to_email, campaign.subject, body_html, pdf_path)
                if success:
                    break
                else:
                    self.storage.update_queue_status(doc_id, QueueState.RETRYING, f"Attempt {attempt} failed")
                    self.reconnect_server()
                    time.sleep(2) # Short delay between immediate retries
                    
            if success:
                self.storage.update_queue_status(doc_id, QueueState.SENT)
                sent += 1
                successful_sends_since_reconnect += 1
                
                # Logic to reconnect after X emails to prevent SMTP throttling
                if successful_sends_since_reconnect >= config.RECONNECT_AFTER:
                    self.reconnect_server()
                    successful_sends_since_reconnect = 0
                    
                time.sleep(config.SEND_DELAY)
            else:
                self.storage.update_queue_status(doc_id, QueueState.FAILED, "Max retries exceeded")
                failed += 1
                
        duration = time.time() - start_time
        return EmailResult(True, sent, failed, duration, [])
