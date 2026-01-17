"""Centralized logging configuration for CC++ PII Masking System.

This module provides:
- Custom TRACE level (5) for ultra-verbose debugging
- Config-driven logging setup from default.yaml
- Suppression of noisy third-party loggers (httpx, httpcore)
- Structured log formatting
"""

import logging
import sys
from typing import Optional

# Custom TRACE level - below DEBUG for ultra-verbose logging
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def trace(self, message: str, *args, **kwargs) -> None:
    """Log at TRACE level (below DEBUG)."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


# Add trace method to Logger class
logging.Logger.trace = trace


# Default format for logs
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
STRUCTURED_FORMAT = "%(asctime)s [%(levelname)-5s] [%(name)s] %(message)s"


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = "/tmp/gui_debug.log",
    trace_enabled: bool = False,
    suppress_httpx: bool = True,
    structured: bool = False,
) -> None:
    """Configure logging for the CC++ application.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file, or None to disable file logging
        trace_enabled: If True, enable TRACE level (below DEBUG)
        suppress_httpx: If True, suppress httpx/httpcore verbose logs
        structured: If True, use structured format with logger names
    """
    # Determine effective level
    if trace_enabled:
        effective_level = TRACE
    else:
        effective_level = getattr(logging, level.upper(), logging.INFO)

    # Choose format
    log_format = STRUCTURED_FORMAT if structured else DEFAULT_FORMAT

    # Configure handlers
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    # Apply basic config
    logging.basicConfig(
        level=effective_level,
        format=log_format,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Suppress noisy third-party loggers
    if suppress_httpx:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("anthropic").setLevel(logging.WARNING)

    # Log the configuration (at DEBUG so it's visible when debugging)
    logger = logging.getLogger(__name__)
    logger.debug(
        f"[logging] configured: level={level} trace={trace_enabled} "
        f"file={log_file} suppress_httpx={suppress_httpx}"
    )


def configure_from_config(config) -> None:
    """Configure logging from a Config object.

    Args:
        config: Config object with logging section (from load_config())
    """
    logging_config = getattr(config, "logging", None)
    if logging_config is None:
        # Fallback to defaults
        configure_logging()
        return

    # Extract settings from config
    level = getattr(logging_config, "level", "INFO")
    trace_enabled = getattr(logging_config, "trace_enabled", False)
    log_file = getattr(logging_config, "log_file", "/tmp/gui_debug.log")
    suppress_httpx = getattr(logging_config, "suppress_httpx", True)
    structured = getattr(logging_config, "structured", False)

    configure_logging(
        level=level,
        log_file=log_file,
        trace_enabled=trace_enabled,
        suppress_httpx=suppress_httpx,
        structured=structured,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    This is a convenience function that ensures the logger
    has the trace method available.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured Logger instance
    """
    return logging.getLogger(name)
