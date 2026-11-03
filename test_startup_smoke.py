"""Startup smoke test for BOPEL UI.

Ensures required assets exist and app can be imported without crashing.
"""
import os
import subprocess
import sys

def test_assets_exist():
    required = [
        "web/index.html",
        "web/style.css",
        "web/app.js",
        "config.yaml",
        "app.py",
        "start.bat",
        "check.py",
        "scan.py",
        "shopee_fetch.py",
        "screenshot_iklan.py",
        "core/caption.py",
        "core/config.py",
        "core/launcher.py",
        "core/logger.py",
        "core/observ.py",
        "core/parsing.py",
        "core/system.py",
        "core/validasi.py",
        "core/window.py",
    ]
    missing = [p for p in required if not os.path.exists(p)]
    assert not missing, f"Missing required files: {missing}"

def test_import_app_and_path():
    # Import app in a subprocess to avoid side effects
    code = (
        "import app, pathlib, sys; "
        "p = app._web_index_path(); "
        "print('INDEX:', p); "
        "assert p.is_file(), 'index.html not found'; "
    )
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"Import app failed: {res.stdout}\n{res.stderr}"
    assert "INDEX:" in res.stdout

if __name__ == "__main__":
    test_assets_exist()
    test_import_app_and_path()
    print("✅ Startup smoke test PASS")
