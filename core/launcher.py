"""Tool launcher — runs external Python scripts as subprocesses.

Each tool runs as an isolated child process.  stdout/stderr are piped
back to the Textual UI via a reader thread that posts ToolOutput
messages line-by-line.  The Stop button calls terminate() then kill()
on the subprocess so the child is actually stopped, not just the UI.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from textual.app import App
from textual.message import Message

from core.config import Config
from core.logger import AppLogger


# ── Textual messages emitted by the launcher ──────────────────────────
class ToolOutput(Message):
    def __init__(self, text: str, worker_id: str = "") -> None:
        super().__init__()
        self.text = text
        self.worker_id = worker_id


class ToolStarted(Message):
    def __init__(self, tool_name: str, worker_id: str = "") -> None:
        super().__init__()
        self.tool_name = tool_name
        self.worker_id = worker_id


class ToolFinished(Message):
    def __init__(self, tool_name: str, success: bool = True,
                 return_code: int = 0, error: str = "",
                 worker_id: str = "") -> None:
        super().__init__()
        self.tool_name = tool_name
        self.success = success
        self.return_code = return_code
        self.error = error
        self.worker_id = worker_id


# ── Data class for tracking a running tool ────────────────────────────
@dataclass
class ToolRunner:
    tool_name: str
    script_path: str
    process: subprocess.Popen | None = None
    reader_thread: threading.Thread | None = None
    running: bool = False
    start_time: float = 0.0


# ── Main launcher ─────────────────────────────────────────────────────
class ToolLauncher:
    """Manages tool discovery, validation, and execution."""

    def __init__(self) -> None:
        self.active_tools: dict[str, ToolRunner] = {}

    @staticmethod
    def resolve_script(script_name: str) -> Path:
        path = Config.tools_dir() / script_name
        if not path.exists():
            raise FileNotFoundError(f"Script not found: {path}")
        return path

    def find_tool_config(self, script_name: str) -> dict | None:
        for t in Config.tools():
            if t.get("script") == script_name:
                return t
        return None

    def start(self, script_name: str, app: App) -> bool:
        """Launch a tool script as a subprocess.

        Returns True on success, False if already running or script not found.
        """
        if script_name in self.active_tools and self.active_tools[script_name].running:
            AppLogger.warning(f"Tool already running: {script_name}")
            return False

        try:
            script_path = self.resolve_script(script_name)
        except FileNotFoundError:
            AppLogger.error(f"Script not found: {script_name}")
            app.post_message(ToolOutput(f"[ERROR] Script not found: {script_name}"))
            app.post_message(ToolFinished(script_name, success=False, error="Script not found"))
            return False

        tool_cfg = self.find_tool_config(script_name)
        display_name = tool_cfg["name"] if tool_cfg else script_name

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
        env = dict(os.environ)
        env["BOPEL_UI_MODE"] = "1"
        env["PYTHONUTF8"] = "1"

        # Create subprocess with piped stdout+stderr
        try:
            process = subprocess.Popen(
                [sys.executable, "-u", str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(script_path.parent),
                startupinfo=startupinfo,
                creationflags=creationflags,
                env=env,
            )
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            AppLogger.error(f"Failed to start {display_name}: {error_msg}")
            app.post_message(ToolOutput(f"[ERROR] {error_msg}"))
            app.post_message(ToolFinished(display_name, success=False, error=error_msg))
            return False

        runner = ToolRunner(
            tool_name=display_name,
            script_path=str(script_path),
            process=process,
            running=True,
        )
        self.active_tools[script_name] = runner

        AppLogger.info(f"Starting tool: {display_name} (pid={process.pid})")
        app.post_message(ToolStarted(display_name, worker_id=script_name))

        # Reader thread: reads stdout line-by-line, posts messages
        reader = threading.Thread(
            target=self._read_output,
            args=(app, script_name, runner),
            daemon=True,
        )
        runner.reader_thread = reader
        reader.start()
        return True

    def stop(self, script_name: str) -> None:
        """Terminate a running tool's subprocess."""
        runner = self.active_tools.get(script_name)
        if not runner or not runner.process:
            return

        proc = runner.process
        if proc.poll() is None:
            AppLogger.info(f"Stopping tool: {runner.tool_name} (pid={proc.pid})")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                AppLogger.warning(f"Force-killing {runner.tool_name} (pid={proc.pid})")
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass

        runner.running = False
        self.active_tools.pop(script_name, None)

    # ── reader thread target ──────────────────────────────────────────
    @staticmethod
    def _read_output(app: App, script_name: str, runner: ToolRunner) -> None:
        """Read subprocess stdout line-by-line and post ToolOutput messages."""
        proc = runner.process
        if proc is None or proc.stdout is None:
            return

        try:
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if line:
                    app.post_message(ToolOutput(line, worker_id=script_name))
        except Exception:
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

        # Process has exited — get the return code reliably
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

        return_code = proc.returncode if proc.returncode is not None else 0
        success = return_code == 0

        if success:
            AppLogger.success(f"Tool finished: {runner.tool_name}")
        else:
            AppLogger.error(f"Tool failed: {runner.tool_name} (exit code {return_code})")

        runner.running = False
        app.post_message(ToolFinished(
            runner.tool_name,
            success=success,
            return_code=return_code or 0,
            worker_id=script_name,
        ))
