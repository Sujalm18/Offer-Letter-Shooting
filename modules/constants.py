import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
GENERATED_DIR = os.path.join(BASE_DIR, "generated")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

DB_PATH = os.path.join(DATA_DIR, "database.db")
DOCUMENT_TYPES_CONFIG = os.path.join(CONFIG_DIR, "document_types.yaml")

# Theme Colors
PRIMARY_COLOR = "#1F2D5C"
ACCENT_COLOR = "#2E5BFF"
BG_COLOR = "#F7F9FC"
CARD_BG = "#FFFFFF"

# Queue States
class QueueState:
    QUEUED = "Queued"
    GENERATING = "Generating"
    GENERATED = "Generated"
    SENDING = "Sending"
    SENT = "Sent"
    RETRYING = "Retrying"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"
    PAUSED = "Paused"

class LogLevel:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
