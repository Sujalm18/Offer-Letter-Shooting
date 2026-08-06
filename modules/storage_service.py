import sqlite3
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
from modules.constants import DB_PATH, QueueState
from modules.models import CampaignData, DocumentData

class StorageServiceInterface:
    def initialize_db(self): pass
    def create_campaign(self, campaign: CampaignData) -> str: pass
    def get_campaign(self, campaign_id: str) -> Optional[CampaignData]: pass
    def save_documents_and_queue_transaction(self, campaign_id: str, documents: List[DocumentData]) -> bool: pass
    def update_queue_status(self, doc_id: str, status: str, error_msg: Optional[str] = None): pass
    def get_pending_queue(self, campaign_id: str) -> List[Dict]: pass
    def write_log(self, campaign_id: Optional[str], level: str, origin: str, message: str): pass
    def save_email_template(self, name: str, subject: str, body: str): pass
    def get_email_templates(self) -> List[Dict]: pass
    def get_email_template(self, name: str) -> Optional[Dict]: pass
    def search_documents(self, query: str) -> List[Dict]: pass
    def update_campaign_status(self, campaign_id: str, status: str): pass

class SQLiteStorageService(StorageServiceInterface):
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.initialize_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def initialize_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    doc_type TEXT,
                    client TEXT,
                    subject TEXT,
                    body_template TEXT,
                    template_version TEXT,
                    status TEXT,
                    created_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT,
                    doc_number TEXT,
                    candidate_name TEXT,
                    email TEXT,
                    pdf_path TEXT,
                    docx_path TEXT,
                    status TEXT,
                    variables TEXT,
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_queue (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    campaign_id TEXT,
                    email TEXT,
                    status TEXT,
                    retry_count INTEGER DEFAULT 0,
                    last_attempt TIMESTAMP,
                    error_msg TEXT,
                    FOREIGN KEY(doc_id) REFERENCES documents(id),
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT,
                    timestamp TIMESTAMP,
                    level TEXT,
                    origin TEXT,
                    message TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_templates (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    subject TEXT,
                    body TEXT
                )
            """)
            conn.commit()

    def create_campaign(self, campaign: CampaignData) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO campaigns (id, name, doc_type, client, subject, body_template, template_version, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (campaign.id, campaign.name, campaign.doc_type, campaign.client, campaign.subject, campaign.body_template, campaign.template_version, campaign.status, campaign.created_at)
            )
            conn.commit()
        return campaign.id

    def get_campaign(self, campaign_id: str) -> Optional[CampaignData]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if row:
                return CampaignData(
                    id=row[0], name=row[1], doc_type=row[2], client=row[3], subject=row[4],
                    body_template=row[5], template_version=row[6], status=row[7],
                    created_at=row[8], completed_at=row[9]
                )
        return None

    def update_campaign_status(self, campaign_id: str, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status == "Completed":
                cursor.execute("UPDATE campaigns SET status = ?, completed_at = ? WHERE id = ?", (status, datetime.now(), campaign_id))
            else:
                cursor.execute("UPDATE campaigns SET status = ? WHERE id = ?", (status, campaign_id))
            conn.commit()

    def save_documents_and_queue_transaction(self, campaign_id: str, documents: List[DocumentData]) -> bool:
        """Saves offers and inserts into email_queue in a single transaction."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for doc in documents:
                    cursor.execute(
                        "INSERT INTO documents (id, campaign_id, doc_number, candidate_name, email, pdf_path, docx_path, status, variables) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (doc.id, campaign_id, doc.doc_number, doc.candidate_name, doc.email, doc.pdf_path, doc.docx_path, doc.status, json.dumps(doc.variables))
                    )
                    queue_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO email_queue (id, doc_id, campaign_id, email, status, retry_count) VALUES (?, ?, ?, ?, ?, ?)",
                        (queue_id, doc.id, campaign_id, doc.email, QueueState.QUEUED, 0)
                    )
                conn.commit()
            return True
        except sqlite3.Error as e:
            # Transaction is rolled back automatically
            print(f"Transaction failed: {e}")
            return False

    def update_queue_status(self, doc_id: str, status: str, error_msg: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            if error_msg:
                cursor.execute("UPDATE email_queue SET status = ?, last_attempt = ?, error_msg = ?, retry_count = retry_count + 1 WHERE doc_id = ?", (status, now, error_msg, doc_id))
            else:
                cursor.execute("UPDATE email_queue SET status = ?, last_attempt = ? WHERE doc_id = ?", (status, now, doc_id))
            conn.commit()

    def update_document_status(self, doc_id: str, status: str, pdf_path: Optional[str] = None, docx_path: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE documents SET status = ?, pdf_path = coalesce(?, pdf_path), docx_path = coalesce(?, docx_path) WHERE id = ?", (status, pdf_path, docx_path, doc_id))
            conn.commit()

    def get_pending_queue(self, campaign_id: str) -> List[Dict]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT q.*, d.pdf_path, d.candidate_name, d.variables FROM email_queue q JOIN documents d ON q.doc_id = d.id WHERE q.campaign_id = ? AND q.status IN (?, ?, ?)", 
                           (campaign_id, QueueState.QUEUED, QueueState.GENERATED, QueueState.RETRYING))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def write_log(self, campaign_id: Optional[str], level: str, origin: str, message: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            log_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO activity_logs (id, campaign_id, timestamp, level, origin, message) VALUES (?, ?, ?, ?, ?, ?)",
                (log_id, campaign_id, datetime.now(), level, origin, message)
            )
            conn.commit()

    def save_email_template(self, name: str, subject: str, body: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            id_ = str(uuid.uuid4())
            cursor.execute(
                "INSERT OR REPLACE INTO email_templates (id, name, subject, body) VALUES (COALESCE((SELECT id FROM email_templates WHERE name = ?), ?), ?, ?, ?)",
                (name, id_, name, subject, body)
            )
            conn.commit()

    def get_email_templates(self) -> List[Dict]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM email_templates")
            return [dict(row) for row in cursor.fetchall()]

    def get_email_template(self, name: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM email_templates WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def search_documents(self, query: str) -> List[Dict]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            like_query = f"%{query}%"
            cursor.execute(
                "SELECT d.*, c.name as campaign_name FROM documents d JOIN campaigns c ON d.campaign_id = c.id WHERE candidate_name LIKE ? OR email LIKE ? OR doc_number LIKE ?", 
                (like_query, like_query, like_query)
            )
            return [dict(row) for row in cursor.fetchall()]
