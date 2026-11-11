"""Startup smoke test for BOPEL Pywebview SPA.

Ensures required pywebview files exist and app can be loaded successfully.
"""
import os
import subprocess
import sys

def test_pywebview_files_exist():
    required = [
        "main.py",
        "ui/app.py",
        "ui/dashboard.py",
        "ui/sidebar.py",
        "ui/panels.py",
        "config.yaml",
        "start.bat",
        "check.py",
        "scan.py",
        "shopee_fetch.py",
        "screenshot_iklan.py",
        "core/caption.py",
        "core/clipboard.py",
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
    assert not missing, f"Missing required Pywebview files: {missing}"

def test_import_ui_app():
    code = (
        "import ui.app; "
        "print('UI App imported successfully'); "
    )
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"Import ui.app failed: {res.stdout}\n{res.stderr}"
    assert "UI App imported successfully" in res.stdout

def test_config_and_modes():
    from core.config import Config
    Config.load()
    tools = Config.tools()
    assert len(tools) > 0
    # Verify Inventory Scanner has 2 modes
    scan_tool = next((t for t in tools if t.get("script") == "scan.py"), None)
    assert scan_tool is not None
    modes = scan_tool.get("modes", [])
    mode_names = [m["name"] for m in modes]
    assert "Scan Kode Pesanan" in mode_names
    assert "Scan Detail" in mode_names

if __name__ == "__main__":
    test_pywebview_files_exist()
    test_import_ui_app()
    test_config_and_modes()
    print("✅ Startup smoke test Pywebview PASS")
