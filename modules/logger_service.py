import os
from loguru import logger
from datetime import datetime
from modules.constants import LogLevel

class LoggerService:
    """
    Structured logging service that handles file and console logging.
    Can be dynamically configured to output logs to a specific campaign directory.
    """
    def __init__(self):
        # Configure default logger
        logger.remove()
        
        # Console sink
        logger.add(
            sink=lambda msg: print(msg, end=""),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[service]}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        self.campaign_log_path = None
        self.campaign_handler_id = None
        self.db_callback = None

    def set_db_callback(self, callback):
        """Allows injecting a callback to save logs to the database."""
        self.db_callback = callback

    def set_campaign_log(self, campaign_dir: str):
        """Adds a file sink for a specific campaign."""
        if self.campaign_handler_id:
            try:
                logger.remove(self.campaign_handler_id)
            except ValueError:
                pass
        
        log_dir = os.path.join(campaign_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.campaign_log_path = os.path.join(log_dir, "Logs.txt")
        
        self.campaign_handler_id = logger.add(
            sink=self.campaign_log_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[service]} - {message}",
            level="INFO"
        )

    def _log(self, level: str, service: str, message: str, campaign_id: str = None):
        """Internal logging method that also writes to the database if configured."""
        bound_logger = logger.bind(service=service)
        
        if level == LogLevel.INFO:
            bound_logger.info(message)
        elif level == LogLevel.WARNING:
            bound_logger.warning(message)
        elif level == LogLevel.ERROR:
            bound_logger.error(message)
        elif level == LogLevel.CRITICAL:
            bound_logger.critical(message)
            
        if self.db_callback:
            self.db_callback(campaign_id, level, service, message)

    def info(self, service: str, message: str, campaign_id: str = None):
        self._log(LogLevel.INFO, service, message, campaign_id)

    def warning(self, service: str, message: str, campaign_id: str = None):
        self._log(LogLevel.WARNING, service, message, campaign_id)

    def error(self, service: str, message: str, campaign_id: str = None):
        self._log(LogLevel.ERROR, service, message, campaign_id)

    def critical(self, service: str, message: str, campaign_id: str = None):
        self._log(LogLevel.CRITICAL, service, message, campaign_id)

# Singleton instance
log_service = LoggerService()
