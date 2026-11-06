"""Utility function to resolve store name from screenshot filename.
Used across caption generation, clipboard handling, and UI.
"""

from __future__ import annotations

from pathlib import Path
import re

from core.config import Config


def nama_bersih_dari_config(nama_config: str) -> str:
    """Normalize store name from config entry.
    Removes leading "Toko <num> —" or "Toko <num> -" prefixes, replaces multiple spaces, trims.
    """
    cleaned = re.sub(r'^.*?[\-—]\s*', '', nama_config)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def nama_toko_dari_file(path: str | Path) -> str | None:
    """Extract store name from a screenshot file path.

    Rules:
    * Replace underscores with spaces, lower‑case.
    * Remove leading ``toko <num> `` (e.g. ``toko 1 ``) if present.
    * Match the longest store name from ``config.yaml`` ``stores`` list.
    * Return the matched store name (original case from config) if found.
    * If no match, log a warning and return ``None``.
    """
    Config.ensure_loaded()
    p = Path(path)
    stem = p.stem
    raw = stem.replace('_', ' ').lower()
    if '—' in raw:
        raw = raw.split('—', 1)[1].strip()

    raw = raw.strip()
    if raw.startswith('toko '):
        parts = raw.split(' ', 2)
        if len(parts) >= 3 and parts[1].isdigit():
            raw = parts[2]
    raw = raw.strip()
    best_match: str | None = None
    for s in Config.stores():
        name = s.get('name')
        if not name:
            continue
        clean_name = re.sub(r'^.*?[\-—]\s*', '', name)
        lowered = clean_name.strip().lower()
        if lowered in raw:
            if best_match is None or len(name) > len(best_match):
                best_match = name
    if not best_match:
        print(f"[WARN] Tidak dapat menemukan nama toko untuk file: {path}")
    if best_match:
        if '—' in best_match:
            return best_match.split('—', 1)[1].strip()
        elif '-' in best_match:
            return best_match.split('-', 1)[1].strip()
        else:
            return best_match.strip()
    return None
