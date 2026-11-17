"""Configuration loader — reads config.yaml and provides typed access."""

import os
import yaml
from pathlib import Path


_BASE = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Config.yaml tidak valid — field wajib hilang / tipe salah."""


class Config:
    """Singleton config holder. Call Config.load() once at startup.

    VALIDASI (2026-08-12): load() memvalidasi struktur config.yaml dan
    RAISE ConfigError dengan pesan lengkap kalau ada field wajib yang
    hilang / salah tipe. Sebelumnya field yang salah/salah tipe DIAM-DIAM
    diabaikan (silent fail) -> sidebar kosong / crash aneh pas klik tool.
    """

    _data: dict = {}

    @classmethod
    def ensure_loaded(cls, path: str | Path | None = None) -> dict:
        """Pastikan config sudah di-load (dipakai tool subprocess yang gak
        lewat BopelApp.__init__, mis. check.py/scan.py). No-op kalau sudah."""
        if not cls._data:
            return cls.load(path)
        return cls._data

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

        masalah = cls.validate()
        if masalah:
            daftar = "\n".join(f"  - {m}" for m in masalah)
            raise ConfigError(
                f"config.yaml ('{path}') tidak valid:\n{daftar}\n"
                "Perbaiki file config dulu (lihat docs/CONFIG_SCHEMA.md), lalu jalankan lagi."
            )
        return cls._data

    @classmethod
    def validate(cls) -> list[str]:
        """Cek struktur config. Return daftar masalah (kosong = valid)."""
        masalah: list[str] = []
        data = cls._data

        if not isinstance(data, dict):
            return ["isi config.yaml harus berbentuk mapping (key: value) di level teratas"]

        app = data.get("app")
        if not isinstance(app, dict):
            masalah.append("app: wajib ada, berbentuk mapping (berisi name/version/subtitle)")
        else:
            for key in ("name", "version", "subtitle"):
                if not isinstance(app.get(key), str):
                    masalah.append(f"app.{key}: wajib string")
            if isinstance(app.get("name"), str) and not app["name"].strip():
                masalah.append("app.name: wajib string tidak kosong")

        tools = data.get("tools", [])
        if not isinstance(tools, list):
            masalah.append("tools: wajib list (bisa kosong)")
        else:
            for i, t in enumerate(tools):
                if not isinstance(t, dict):
                    masalah.append(f"tools[{i}]: wajib mapping (name/script/description)")
                    continue
                for key in ("name", "script"):
                    if not isinstance(t.get(key), str) or not str(t.get(key, "")).strip():
                        masalah.append(f"tools[{i}].{key}: wajib string tidak kosong")
                if "description" in t and not isinstance(t["description"], str):
                    masalah.append(f"tools[{i}].description: wajib string")
                if "target_window_title" in t and not isinstance(t["target_window_title"], str):
                    masalah.append(f"tools[{i}].target_window_title: wajib string kalau ada")
                # Kelompok D: 1 tool bisa punya beberapa MODE eksekusi
                # (opsional). tools[].modes = list mapping {name, description?,
                # script?}. script kosong = pakai script tool induknya.
                if "modes" in t:
                    modes = t["modes"]
                    if not isinstance(modes, list) or not modes:
                        masalah.append(f"tools[{i}].modes: wajib list tidak kosong kalau ada")
                    else:
                        for j, m in enumerate(modes):
                            if not isinstance(m, dict):
                                masalah.append(f"tools[{i}].modes[{j}]: wajib mapping (name/script/description)")
                                continue
                            if not isinstance(m.get("name"), str) or not str(m.get("name", "")).strip():
                                masalah.append(f"tools[{i}].modes[{j}].name: wajib string tidak kosong")
                            if "description" in m and not isinstance(m["description"], str):
                                masalah.append(f"tools[{i}].modes[{j}].description: wajib string")
                            if "script" in m and not isinstance(m["script"], str):
                                masalah.append(f"tools[{i}].modes[{j}].script: wajib string")

        logging = data.get("logging")
        if logging is not None and not isinstance(logging, dict):
            masalah.append("logging: wajib mapping (level/file) kalau ada")
        elif isinstance(logging, dict):
            if not isinstance(logging.get("level"), str):
                masalah.append("logging.level: wajib string (mis. INFO)")
            if not isinstance(logging.get("file"), str):
                masalah.append("logging.file: wajib string (mis. logs/app.log)")

        # Auto-Fetch Shopee (2026-08-19): daftar toko untuk selector UI.
        # Semua toko enabled = aktif & bisa dipilih di UI.
        stores = data.get("stores", [])
        if not isinstance(stores, list):
            masalah.append("stores: wajib list (bisa kosong)")
        else:
            for i, s in enumerate(stores):
                if not isinstance(s, dict):
                    masalah.append(f"stores[{i}]: wajib mapping (name/enabled/...)")
                    continue
                if not isinstance(s.get("name"), str) or not str(s.get("name", "")).strip():
                    masalah.append(f"stores[{i}].name: wajib string tidak kosong")
                if "enabled" in s and not isinstance(s["enabled"], bool):
                    masalah.append(f"stores[{i}].enabled: wajib boolean kalau ada")
                if "chrome_user_data_dir" in s and not isinstance(s["chrome_user_data_dir"], str):
                    masalah.append(f"stores[{i}].chrome_user_data_dir: wajib string kalau ada")
                if "profile_directory" in s and not isinstance(s["profile_directory"], str):
                    masalah.append(f"stores[{i}].profile_directory: wajib string kalau ada")
                if "shortcut" in s and not isinstance(s["shortcut"], str):
                    masalah.append(f"stores[{i}].shortcut: wajib string kalau ada")
                if s.get("enabled") and not str(s.get("shortcut") or "").strip():
                    masalah.append(f"stores[{i}].shortcut: wajib diisi (path .lnk toko) untuk toko enabled")

        return masalah

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
    def modes(cls, script_name: str) -> list[dict]:
        """Modes tool dari config.yaml (kosong = tool tanpa mode).

        Kelompok D: `tools[].modes` — daftar varian eksekusi 1 tool
        (Inventory Scanner: Scan Kecil / Scan Detail / Scan Bulanan).
        Dipakai launcher/UI untuk render tombol per mode & resolve
        script mode (script kosong = pakai script tool induk).
        """
        for t in cls.tools():
            if t.get("script") == script_name:
                modes = t.get("modes")
                if isinstance(modes, list):
                    return modes
                return []
        return []

    @classmethod
    def stores(cls) -> list[dict]:
        """Daftar toko Shopee untuk Auto-Fetch (2026-08-19).

        `stores:` di config.yaml — nambah toko baru = edit config saja
        (pola yang sama dengan tools[].modes). Source of truth lokasi
        profile Chrome toko ada di sini (dari investigasi shortcut .lnk,
        diverifikasi ulang 2026-08-20: Toko 1 = Profile 7, Toko 2 BSM =
        Profile 10, Toko 3 Medika = Profile 9).
        """
        stores = cls.get("stores", default=[])
        return stores if isinstance(stores, list) else []

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
