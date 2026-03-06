import logging
import os
from logging.handlers import TimedRotatingFileHandler

def setup_logger(log_level: str = None, log_dir: str = None):
    log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
    log_dir = log_dir or os.getenv('LOG_DIR', '/app/logs')
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s - %(message)s')
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    if not root.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)
        fh = TimedRotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            when='midnight', backupCount=7, encoding='utf-8'
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def setup_logging(app):
    setup_logger(
        log_level=app.config.get('LOG_LEVEL', 'INFO'),
        log_dir=app.config.get('LOG_DIR', '/app/logs')
    )
