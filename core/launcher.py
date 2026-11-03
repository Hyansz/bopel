"""Tool launcher — runs external Python scripts as subprocesses.

Each tool runs as an isolated child process.  stdout/stderr are piped
back line-by-line via the ``on_output`` callback (reader thread).  Stop
calls terminate() then kill() on the subprocess so the child is actually
stopped, not just the UI.

UI-agnostic (refactor Fase 2 migrasi pywebview): launcher tidak lagi
mengenal Textual / post_message — pemanggil mengirim callback
``on_output(line)``, ``on_started(tool_name)``, ``on_finished(tool_name,
success, return_code, error)``. Textual (ui/app.py) membungkus callback
menjadi post_message; pywebview (app.py) memakai callback langsung.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.config import Config
from core.logger import AppLogger


# ── callback signatures ──────────────────────────────────────────────
OnOutput = Callable[[str], None]                             # line
OnStarted = Callable[[str], None]                            # tool_name
OnFinished = Callable[[str, bool, int, str], None]           # tool_name, success, return_code, error


# ── Data class for tracking a running tool ────────────────────────────
@dataclass
class ToolRunner:
    tool_name: str
    script_path: str
    process: subprocess.Popen | None = None
    running: bool = False


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

    def start(
        self,
        script_name: str,
        on_output: OnOutput | None = None,
        on_started: OnStarted | None = None,
        on_finished: OnFinished | None = None,
    ) -> bool:
        """Launch a tool script as a subprocess.

        Returns True on success, False if already running or script not found.
        Output/finish dikirim lewat callback (bukan post_message Textual).
        """
        if script_name in self.active_tools and self.active_tools[script_name].running:
            AppLogger.warning(f"Tool already running: {script_name}")
            return False

        try:
            script_path = self.resolve_script(script_name)
        except FileNotFoundError:
            AppLogger.error(f"Script not found: {script_name}")
            if on_output:
                on_output(f"[ERROR] Script not found: {script_name}")
            if on_finished:
                on_finished(script_name, False, 0, "Script not found")
            return False

        tool_cfg = self.find_tool_config(script_name)
        display_name = tool_cfg["name"] if tool_cfg else script_name

        # Tool jalan HIDDEN (tanpa window CMD terpisah) + mode non-interaktif:
        # - CREATE_NO_WINDOW (Windows): child gak dapat console sendiri,
        #   jadi gak ada window CMD yang muncul. Output tetap ke stdout PIPE
        #   yang di-stream ke pemanggil, dan Stop (terminate/kill) tetap normal.
        # - env BOPEL_UI_MODE=1: tool tau dia dijalankan dari UI -> semua
        #   prompt input() (yang gak bisa dijawab dari window) di-skip /
        #   auto-continue, dan aktivasi window warehouse dilakukan otomatis
        #   (lihat core/window.py).
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
        env = dict(os.environ)
        env["BOPEL_UI_MODE"] = "1"
        # WAJIB: stdout child di-stream via PIPE (bukan console). Di Windows,
        # Python child yang stdout-nya pipe default-nya pakai encoding cp1252
        # -> print("✔") / print("⚠") (banyak dipakai di check.py & scan.py)
        # bikin UnicodeEncodeError CRASH pas dijalankan dari UI. PYTHONUTF8=1
        # memaksa UTF-8 buat stdout/stderr pipe.
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
            if on_output:
                on_output(f"[ERROR] {error_msg}")
            if on_finished:
                on_finished(display_name, False, 0, error_msg)
            return False

        runner = ToolRunner(
            tool_name=display_name,
            script_path=str(script_path),
            process=process,
            running=True,
        )
        self.active_tools[script_name] = runner

        AppLogger.info(f"Starting tool: {display_name} (pid={process.pid})")
        if on_started:
            on_started(display_name)

        # Reader thread: reads stdout line-by-line, invokes on_output
        threading.Thread(
            target=self._read_output,
            args=(script_name, runner, on_output, on_finished),
            daemon=True,
        ).start()
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
    def _read_output(
        script_name: str,
        runner: ToolRunner,
        on_output: OnOutput | None,
        on_finished: OnFinished | None,
    ) -> None:
        """Read subprocess stdout line-by-line and invoke on_output."""
        proc = runner.process
        if proc is None or proc.stdout is None:
            return

        try:
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if line and on_output:
                    on_output(line)
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
        if on_finished:
            on_finished(runner.tool_name, success, return_code, "")
