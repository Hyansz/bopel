"""Main Textual application — ties core modules and UI screens together."""

from __future__ import annotations

import sys
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from core.config import Config
from core.launcher import ToolFinished, ToolLauncher, ToolOutput, ToolStarted
from core.logger import AppLogger
from ui.dashboard import (
    CSS,
    DashboardScreen,
    LogScreen,
    SettingsScreen,
    Splash,
    ToolScreen,
)
from ui.sidebar import MenuSelected


class BopelApp(App):
    """Top-level Textual application."""

    TITLE = "Bopel Automation Toolkit"
    SUB_TITLE = "Internal Warehouse Utilities"
    CSS = CSS
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        Config.load()
        self.launcher = ToolLauncher()
        self._global_log: list[str] = []
        self._active_tool_screen: ToolScreen | None = None

    def config_get(self, *keys, default=None):
        return Config.get(*keys, default=default)

    # ── startup ────────────────────────────────────────────────────
    def on_mount(self) -> None:
        AppLogger.info("Application started")
        AppLogger.info(f"Python {sys.version.split()[0]}  |  {sys.platform}")
        self.push_screen(Splash())

    # ── route sidebar navigation ───────────────────────────────────
    def on_menu_selected(self, event: MenuSelected) -> None:
        if event.action == "logs":
            self._open_log_screen()
        elif event.action == "settings":
            self._open_settings_screen()
        elif event.script_name:
            self._open_tool_screen(event.script_name, event.tool_name)

    def _open_tool_screen(self, script: str, name: str) -> None:
        tool_cfg = next((t for t in Config.tools() if t["script"] == script), {})
        desc = tool_cfg.get("description", "")
        screen = ToolScreen(script, name, desc)
        self._active_tool_screen = screen
        self.push_screen(screen)

    def _open_log_screen(self) -> None:
        screen = LogScreen()
        self.push_screen(screen)
        for line in self._global_log:
            screen.add_line(line)

    def _open_settings_screen(self) -> None:
        self.push_screen(SettingsScreen())

    # ── route launcher messages ────────────────────────────────────
    def on_tool_output(self, event: ToolOutput) -> None:
        line = event.text
        self._global_log.append(line)
        if self._active_tool_screen:
            self._active_tool_screen.handle_tool_output(event.text)

    def on_tool_started(self, event: ToolStarted) -> None:
        self._global_log.append(f"[RUN] {event.tool_name}")
        AppLogger.info(f"Tool started: {event.tool_name}")
        if self._active_tool_screen:
            self._active_tool_screen.handle_tool_started()

    def on_tool_finished(self, event: ToolFinished) -> None:
        if event.success:
            self._global_log.append(f"[OK] {event.tool_name} finished")
            AppLogger.success(f"Tool finished: {event.tool_name}")
        else:
            self._global_log.append(f"[FAIL] {event.tool_name}: {event.error}")
            AppLogger.error(f"Tool failed: {event.tool_name} — {event.error}")
        if self._active_tool_screen:
            self._active_tool_screen.handle_tool_finished(
                success=event.success, error=event.error,
            )

    def action_quit(self) -> None:
        AppLogger.info("Application shutting down")
        self.exit()