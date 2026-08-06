import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SEND_DELAY = int(os.getenv("SEND_DELAY", 30))
    RECONNECT_AFTER = int(os.getenv("RECONNECT_AFTER", 20))
    RETRY_COUNT = int(os.getenv("RETRY_COUNT", 3))

config = Config()
