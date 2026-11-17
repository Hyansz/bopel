"""File-based logger — writes timestamped entries to logs/app.log."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.config import Config


class AppLogger:
    """Thin wrapper around stdlib logging that writes to a rotating file."""

    _logger: logging.Logger | None = None

    @classmethod
    def setup(cls) -> logging.Logger:
        if cls._logger is not None:
            return cls._logger

        log_dir = Config.logs_dir()
        log_file = log_dir / Path(Config.log_file()).name
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger("bopel")
        logger.setLevel(logging.DEBUG)
        if logger.handlers:
            cls._logger = logger
            return logger

        handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
        cls._logger = logger
        return logger

    @classmethod
    def info(cls, msg: str) -> None:
        cls.setup().info(msg)

    @classmethod
    def warning(cls, msg: str) -> None:
        cls.setup().warning(msg)

    @classmethod
    def error(cls, msg: str) -> None:
        cls.setup().error(msg)

    @classmethod
    def debug(cls, msg: str) -> None:
        cls.setup().debug(msg)

    @classmethod
    def success(cls, msg: str) -> None:
        cls.setup().info(f"[OK] {msg}")
