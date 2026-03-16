from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

from utils.config import (
    APP_NAME,
    LOG_BACKUP_COUNT,
    LOG_FILE_NAME,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    ensure_runtime_directories,
    get_log_file_path,
)

# ============================================================
# Logging format
# ============================================================

LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(threadName)s | %(message)s"
)
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def _parse_log_level(level: str | int | None) -> int:
    """
    Convert a log level value to a logging module integer constant.

    Accepted values:
    - None -> default LOG_LEVEL from config
    - str  -> "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    - int  -> logging.DEBUG, logging.INFO, etc.
    """
    if isinstance(level, int):
        return level

    if level is None:
        level = LOG_LEVEL

    if not isinstance(level, str):
        return logging.INFO

    normalized = level.strip().upper()
    return getattr(logging, normalized, logging.INFO)


def _build_formatter() -> logging.Formatter:
    """
    Create the formatter shared by all handlers.
    """
    return logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


def _build_file_handler(log_file_path: Path, level: int) -> RotatingFileHandler:
    """
    Create the rotating file handler.
    """
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(_build_formatter())
    return file_handler


def _build_console_handler(level: int) -> logging.Handler:
    """
    Create the console handler used mainly during development.
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(_build_formatter())
    return console_handler


def setup_logging(
    level: str | int | None = None,
    enable_console: bool = True,
) -> logging.Logger:
    """
    Configure the main application logger.

    This function is idempotent:
    calling it multiple times will not duplicate handlers.

    Returns:
        The configured application logger.
    """
    ensure_runtime_directories()

    logger = logging.getLogger(APP_NAME)
    resolved_level = _parse_log_level(level)
    logger.setLevel(resolved_level)
    logger.propagate = False

    if getattr(logger, "_nodedrop_configured", False):
        return logger

    log_file_path = get_log_file_path()

    file_handler = _build_file_handler(log_file_path, resolved_level)
    logger.addHandler(file_handler)

    if enable_console:
        console_handler = _build_console_handler(resolved_level)
        logger.addHandler(console_handler)

    logger._nodedrop_configured = True  # type: ignore[attr-defined]
    logger.debug(
        "Logging initialized. File='%s', level='%s'",
        log_file_path,
        logging.getLevelName(resolved_level),
    )
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a child logger of the application logger.

    Examples:
        get_logger("core.app_manager")
        get_logger("network.discovery")

    If logging has not been configured yet, it is initialized automatically.
    """
    root_logger = logging.getLogger(APP_NAME)

    if not getattr(root_logger, "_nodedrop_configured", False):
        setup_logging()

    if not name:
        return root_logger

    return root_logger.getChild(name)


def get_log_file() -> Path:
    """
    Return the path of the main log file.
    """
    return get_log_file_path()