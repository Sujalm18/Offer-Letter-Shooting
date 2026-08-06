from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class ValidationResult:
    is_valid: bool
    health_score: float
    total_rows: int
    valid_rows: int
    invalid_emails: int
    duplicates: int
    missing_fields: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    cleaned_df: Optional[Any] = None # Will hold the pandas DataFrame

@dataclass
class GenerationResult:
    success: bool
    generated: int
    failed: int
    duration_secs: float
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class EmailResult:
    success: bool
    sent: int
    failed: int
    duration_secs: float
    errors: List[str] = field(default_factory=list)

@dataclass
class CampaignData:
    id: str
    name: str
    doc_type: str
    client: str
    subject: str
    body_template: str
    template_version: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

@dataclass
class DocumentData:
    id: str
    campaign_id: str
    doc_number: str
    candidate_name: str
    email: str
    pdf_path: Optional[str]
    docx_path: Optional[str]
    status: str
    variables: Dict[str, str] = field(default_factory=dict) # To store all other dynamic variables
