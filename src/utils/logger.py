"""
Logger Setup Utility
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: str = 'binance_bot',
    level: str = 'INFO',
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Setup logger with console and file handlers
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        format_string: Custom format string (optional)
        
    Returns:
        Configured logger instance
    """
    # Configure root logger to capture all logs from child loggers
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers from root logger
    root_logger.handlers.clear()
    
    # Get the named logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers from named logger
    logger.handlers.clear()
    
    # Default format
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    
    # Console handler - add to root logger to capture all child logger messages
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Add color formatter for console output
    try:
        import colorama
        colorama.init()
        from colorama import Fore, Style
        
        class ColorFormatter(logging.Formatter):
            def format(self, record):
                levelno = record.levelno
                if levelno >= logging.ERROR:
                    color = Fore.RED
                elif levelno >= logging.WARNING:
                    color = Fore.YELLOW
                elif levelno >= logging.INFO:
                    color = Fore.GREEN
                else:
                    color = Fore.BLUE
                
                record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
                return super().format(record)
        
        color_formatter = ColorFormatter(format_string)
        console_handler.setFormatter(color_formatter)
    except ImportError:
        # Fallback to default formatter if colorama not installed
        console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    # File handler (if log file specified) - add to root logger
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return logger