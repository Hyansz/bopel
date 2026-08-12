"""Configuration loader — reads config.yaml and provides typed access."""

import os
import yaml
from pathlib import Path


_BASE = Path(__file__).resolve().parent.parent


class Config:
    """Singleton config holder. Call Config.load() once at startup."""

    _data: dict = {}

    @classmethod
    def load(cls, path: str | Path | None = None) -> dict:
        if path is None:
            path = _BASE / "config.yaml"
        else:
            path = Path(path)

        if not path.exists():
            cls._data = cls._defaults()
            cls.save(path)
            return cls._data

        with open(path, "r", encoding="utf-8") as fh:
            cls._data = yaml.safe_load(fh) or {}
        return cls._data

    @classmethod
    def save(cls, path: str | Path | None = None) -> None:
        if path is None:
            path = _BASE / "config.yaml"
        else:
            path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(cls._data, fh, default_flow_style=False, allow_unicode=True)

    # -- nested access --
    @classmethod
    def get(cls, *keys, default=None):
        obj = cls._data
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k)
            else:
                return default
            if obj is None:
                return default
        return obj

    # -- convenience --
    @classmethod
    def app_name(cls) -> str:
        return cls.get("app", "name", default="Bopel Automation Toolkit")

    @classmethod
    def app_version(cls) -> str:
        return cls.get("app", "version", default="0.0.0")

    @classmethod
    def app_subtitle(cls) -> str:
        return cls.get("app", "subtitle", default="Internal Warehouse Utilities")

    @classmethod
    def tools(cls) -> list[dict]:
        return cls.get("tools", default=[])

    @classmethod
    def base_path(cls) -> Path:
        return _BASE

    @classmethod
    def tools_dir(cls) -> Path:
        return _BASE

    @classmethod
    def logs_dir(cls) -> Path:
        d = _BASE / "logs"
        d.mkdir(exist_ok=True)
        return d

    @classmethod
    def log_file(cls) -> str:
        return cls.get("logging", "file", default="logs/app.log")

    @classmethod
    def _defaults(cls) -> dict:
        return {
            "app": {
                "name": "Bopel Automation Toolkit",
                "version": "1.0.0",
                "subtitle": "Internal Warehouse Utilities",
            },
            "tools": [
                {"name": "Checklist Automation", "script": "check.py",
                 "description": "Checklist pesanan dan validasi harga Shopee vs aplikasi"},
                {"name": "Inventory Scanner", "script": "scan.py",
                 "description": "Scan status pembayaran dan validasi Excel"},
            ],
            "logging": {"level": "INFO", "file": "logs/app.log"},
        }
