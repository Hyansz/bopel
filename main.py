"""Bopel Automation Toolkit — entry point.

Run with:  python main.py
Or simply: start.bat
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.app import BopelApp  # noqa: E402


if __name__ == "__main__":
    BopelApp().run()
