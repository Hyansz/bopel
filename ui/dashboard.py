"""Dashboard and tool screens."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Label,
    LoadingIndicator,
    ProgressBar,
    RichLog,
)

from core.config import Config
from core.system import (
    cpu_percent,
    current_date,
    current_time,
    python_version,
    ram_percent,
    ram_used_gb,
    ram_total_gb,
    os_info,
    terminal_name,
)
from ui.sidebar import Sidebar
from ui.panels import HelpPanel

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════
# SHARED CSS
# ═══════════════════════════════════════════════════════════════════════
CSS = """
Screen { background: $surface; }

/* custom header (Textual's built-in Header can't hold custom labels) */
.app-header {
    dock: top; height: 3; background: #181825;
    padding: 0 2; layout: horizontal; align: left middle;
}
.header-title   { text-style: bold; color: #cba6f7; width: 1fr; }
.header-sub     { color: #a6adc8; }
.header-ver     { color: #6c7086; text-style: italic; margin-left: 2; }
.header-time    { color: #89b4fa; text-style: bold; margin-left: 2; }

/* footer */
.app-footer { dock: bottom; height: 1; background: #181825; color: #6c7086; padding: 0 2; }

/* main row: sidebar + content, side by side */
.main-row { height: 1fr; }

/* sidebar */
#sidebar {
    width: 30;
    background: #1e1e2e;
    border-right: tall #313244;
    padding: 1 0;
}
.sidebar-title  { text-style: bold; color: #cba6f7; text-align: left; padding: 0 2 0 2; }
.sidebar-subtitle { color: #6c7086; text-align: left; text-style: italic; padding: 0 2 1 2; width: 100%; }
.sidebar-section { text-style: bold; color: #585b70; padding: 1 2 0 2; }
.menu-btn {
    width: 100%; background: transparent; color: #cdd6f4;
    text-align: left; content-align: left middle; padding: 0 2; min-height: 3; border: none;
}
.menu-btn:hover { background: #313244; color: #89b4fa; }
.menu-btn.-active { background: #45475a; color: #89dceb; text-style: bold; border-left: tall #89b4fa; }

/* dashboard */
.dash-content { height: 1fr; width: 1fr; padding: 1 2; overflow-y: auto; }
.dash-grid {
    layout: grid;
    height: auto;
    grid-size: 2; grid-columns: 1fr 1fr; grid-rows: auto auto;
    grid-gutter: 1 2;
}
.dash-card { background: #1e1e2e; border: round #313244; padding: 1 2; margin: 0; height: auto; }
.dash-card-title { text-style: bold; color: #89b4fa; margin-bottom: 1; }
.dash-label { color: #a6adc8; }
.dash-value { color: #cdd6f4; text-style: bold; }

/* tool screen */
.tool-content { height: 1fr; width: 1fr; padding: 1 2; }
.tool-title { text-style: bold; color: #89b4fa; margin-bottom: 1; }
.tool-desc  { color: #a6adc8; margin-bottom: 1; }
.tool-ctrls { height: auto; margin: 1 0; }
.start-btn {
    background: #a6e3a1; color: #1e1e2e; text-style: bold;
    width: 30; min-height: 3; border: round #94e2d5;
}
.start-btn:hover { background: #94e2d5; }
.start-btn:disabled { background: #45475a; color: #6c7086; border: round #313244; }
.stop-btn {
    background: #f38ba8; color: #1e1e2e; text-style: bold;
    width: 30; min-height: 3; border: round #eba0ac; margin-left: 2;
}
.stop-btn:disabled { background: #45475a; color: #6c7086; border: round #313244; }
.tool-status { color: #a6adc8; margin: 1 0; }
.tool-progress { margin: 0 0 1 0; }
.tool-log { height: 1fr; background: #11111b; border: round #313244; padding: 1; }

/* log screen */
.log-content { height: 1fr; width: 1fr; padding: 1 2; }
.global-log  { height: 1fr; background: #11111b; border: round #313244; padding: 1; }

/* settings */
.settings-content { height: 1fr; width: 1fr; padding: 1 2; }
.settings-card { background: #1e1e2e; border: round #313244; padding: 1 2; margin: 1 0; }

/* splash */
.splash-screen { background: #11111b; }
.splash-content { align: center middle; height: 100%; }
.splash-box {
    width: 60; height: auto; padding: 2 4;
    background: #1e1e2e; border: round #cba6f7; align: center middle;
}
.splash-title    { text-style: bold; color: #cba6f7; text-align: center; margin: 0 0 1 0; }
.splash-subtitle { color: #a6adc8; text-align: center; margin: 0 0 2 0; }
.splash-loader   { margin: 1 0; }
.splash-status   { color: #6c7086; text-align: center; }
"""


def _app_header():
    """Custom header row: title, subtitle, version, live clock.

    Textual's built-in Header widget can't hold custom child labels,
    so every screen composes this instead.
    """
    yield Container(
        Label(Config.app_name(), classes="header-title"),
        Label("Internal Warehouse Utilities", classes="header-sub"),
        Label(f"v{Config.app_version()}", classes="header-ver"),
        Label(current_time(), id="header-time", classes="header-time"),
        classes="app-header",
    )


# ═══════════════════════════════════════════════════════════════════════
# HELP MIXIN — adds the '?' toggle to any Screen that includes it
# ═══════════════════════════════════════════════════════════════════════
class HelpMixin:
    """Mix into a Screen to add a '?'-toggled help panel.

    Subclasses must:
      1. Include Binding("question_mark", "toggle_help", "Help") in BINDINGS
      2. Set HELP_SHORTCUTS = [(key, description), ...]
      3. Compose a HelpPanel(self.HELP_SHORTCUTS, id="help-panel") somewhere
    """

    HELP_SHORTCUTS: list[tuple[str, str]] = []

    def action_toggle_help(self) -> None:
        panel = self.query_one("#help-panel", HelpPanel)
        panel.toggle_class("-visible")


# ═══════════════════════════════════════════════════════════════════════
# SPLASH
# ═══════════════════════════════════════════════════════════════════════
class Splash(Screen):
    CSS = CSS

    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                Label("Bopel Automation Toolkit", classes="splash-title"),
                Label("Internal Warehouse Utilities", classes="splash-subtitle"),
                LoadingIndicator(classes="splash-loader"),
                Label("Initializing...", classes="splash-status"),
                classes="splash-box",
            ),
            classes="splash-content",
        )

    def on_mount(self) -> None:
        self.set_timer(2.5, lambda: (self.app.pop_screen(), self.app.push_screen(DashboardScreen())))


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
class DashboardScreen(HelpMixin, Screen):
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "toggle_help", "Help"),
    ]
    HELP_SHORTCUTS = [
        ("↑ ↓ / klik", "pilih menu di sidebar"),
        ("Enter", "buka tool / halaman yang dipilih"),
        ("Q", "keluar aplikasi"),
        ("?", "tutup panel ini"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._time_label: Label | None = None
        self._cpu_label: Label | None = None
        self._ram_label: Label | None = None

    def compose(self) -> ComposeResult:
        yield from _app_header()
        yield Horizontal(
            Sidebar(id="sidebar"),
            Container(
                Label("Select a tool from the sidebar to get started.", classes="tool-desc"),
                HelpPanel(self.HELP_SHORTCUTS, id="help-panel"),
                Container(
                    Container(
                        Label("System Info", classes="dash-card-title"),
                        Label(f"Python {python_version()}  |  {os_info()}", classes="dash-value"),
                        Label(f"Terminal: {terminal_name()}", classes="dash-label"),
                        Label(f"Date: {current_date()}", classes="dash-label"),
                        classes="dash-card",
                    ),
                    Container(
                        Label("Performance", classes="dash-card-title"),
                        Label("CPU:", classes="dash-label"),
                        Label("--%", id="cpu-val", classes="dash-value"),
                        Label("RAM:", classes="dash-label"),
                        Label("--%", id="ram-val", classes="dash-value"),
                        classes="dash-card",
                    ),
                    Container(
                        Label("Quick Start", classes="dash-card-title"),
                        Label("1. Click a tool in the sidebar", classes="dash-label"),
                        Label("2. Press Start to run", classes="dash-label"),
                        Label("3. Watch the log output", classes="dash-label"),
                        classes="dash-card",
                    ),
                    Container(
                        Label("Shortcuts", classes="dash-card-title"),
                        Label("Q / Esc  = Back / Quit", classes="dash-label"),
                        Label("Click    = Select menu", classes="dash-label"),
                        Label("?        = Panel bantuan", classes="dash-label"),
                        classes="dash-card",
                    ),
                    classes="dash-grid",
                ),
                classes="dash-content",
            ),
            classes="main-row",
        )
        yield Footer(classes="app-footer")

    def on_mount(self) -> None:
        self._time_label = self.query_one("#header-time", Label)
        self._cpu_label = self.query_one("#cpu-val", Label)
        self._ram_label = self.query_one("#ram-val", Label)
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._time_label:
            self._time_label.update(current_time())
        if self._cpu_label:
            self._cpu_label.update(f"{cpu_percent():.0f}%")
        if self._ram_label:
            self._ram_label.update(f"{ram_percent():.0f}%  ({ram_used_gb():.1f}/{ram_total_gb():.1f} GB)")


# ═══════════════════════════════════════════════════════════════════════
# TOOL SCREEN
# ═══════════════════════════════════════════════════════════════════════
class ToolScreen(HelpMixin, Screen):
    CSS = CSS
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "toggle_help", "Help"),
    ]
    HELP_SHORTCUTS = [
        ("Enter", "jalankan tool (saat tombol Start fokus)"),
        ("Esc / Q", "kembali ke dashboard"),
        ("Tab", "pindah fokus antar tombol"),
        ("?", "tutup panel ini"),
    ]

    def __init__(self, script_name: str, tool_name: str, description: str) -> None:
        super().__init__()
        self.script_name = script_name
        self.tool_name = tool_name
        self.description = description
        self._is_running = False

    def compose(self) -> ComposeResult:
        yield from _app_header()
        yield Horizontal(
            Sidebar(id="sidebar"),
            Container(
                Label(self.tool_name, classes="tool-title"),
                Label(self.description, classes="tool-desc"),
                HelpPanel(self.HELP_SHORTCUTS, id="help-panel"),
                Container(
                    Button("Start", id="start-btn", classes="start-btn"),
                    Button("Stop", id="stop-btn", classes="stop-btn", disabled=True),
                    classes="tool-ctrls",
                ),
                Label("Status: Idle", id="tool-status", classes="tool-status"),
                ProgressBar(id="tool-progress", total=100, classes="tool-progress"),
                RichLog(id="tool-log", classes="tool-log", highlight=True, markup=True, auto_scroll=True),
                classes="tool-content",
            ),
            classes="main-row",
        )
        yield Footer(classes="app-footer")

    def on_mount(self) -> None:
        self._log = self.query_one("#tool-log", RichLog)
        self._status = self.query_one("#tool-status", Label)
        self._progress = self.query_one("#tool-progress", ProgressBar)
        self._start_btn = self.query_one("#start-btn", Button)
        self._stop_btn = self.query_one("#stop-btn", Button)

    def action_back(self) -> None:
        if self._is_running:
            self.app.launcher.stop(self.script_name)
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            self._start_tool()
        elif event.button.id == "stop-btn":
            self._stop_tool()

    def _start_tool(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        self._start_btn.disabled = True
        self._stop_btn.disabled = False
        self._status.update("Status: [bold yellow]Running...[/]")
        self._progress.update(progress=0)
        self._log.clear()
        self._log.write(f"[bold cyan]Starting {self.tool_name}...[/]")
        self.app.launcher.start(self.script_name, self.app)

    def _stop_tool(self) -> None:
        self.app.launcher.stop(self.script_name)
        self._finish_tool(success=False, error="Stopped by user")

    def _finish_tool(self, success: bool = True, error: str = "") -> None:
        self._is_running = False
        self._start_btn.disabled = False
        self._stop_btn.disabled = True
        if success:
            self._status.update("Status: [bold green]Finished[/]")
            self._progress.update(progress=100)
            self._log.write("[bold green]Tool finished successfully.[/]")
        else:
            self._status.update(f"Status: [bold red]Failed: {error}[/]")
            self._log.write(f"[bold red]Error: {error}[/]")

    def handle_tool_output(self, text: str) -> None:
        self._log.write(text)

    def handle_tool_started(self) -> None:
        self._progress.update(progress=20)

    def handle_tool_finished(self, success: bool, error: str = "") -> None:
        self._finish_tool(success=success, error=error)


# ═══════════════════════════════════════════════════════════════════════
# LOG SCREEN
# ═══════════════════════════════════════════════════════════════════════
class LogScreen(HelpMixin, Screen):
    CSS = CSS
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "toggle_help", "Help"),
    ]
    HELP_SHORTCUTS = [
        ("Esc / Q", "kembali ke dashboard"),
        ("?", "tutup panel ini"),
    ]

    def compose(self) -> ComposeResult:
        yield from _app_header()
        yield Horizontal(
            Sidebar(id="sidebar"),
            Container(
                Label("Application Log", classes="tool-title"),
                HelpPanel(self.HELP_SHORTCUTS, id="help-panel"),
                RichLog(id="global-log", classes="global-log", highlight=True, markup=True, auto_scroll=True),
                classes="log-content",
            ),
            classes="main-row",
        )
        yield Footer(classes="app-footer")

    def action_back(self) -> None:
        self.app.pop_screen()

    def add_line(self, text: str) -> None:
        self.query_one("#global-log", RichLog).write(text)


# ═══════════════════════════════════════════════════════════════════════
# SETTINGS SCREEN
# ═══════════════════════════════════════════════════════════════════════
class SettingsScreen(HelpMixin, Screen):
    CSS = CSS
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "toggle_help", "Help"),
    ]
    HELP_SHORTCUTS = [
        ("Esc / Q", "kembali ke dashboard"),
        ("?", "tutup panel ini"),
    ]

    def compose(self) -> ComposeResult:
        yield from _app_header()
        yield Horizontal(
            Sidebar(id="sidebar"),
            VerticalScroll(
                Label("Settings", classes="tool-title"),
                Label("Current configuration (read-only).", classes="tool-desc"),
                HelpPanel(self.HELP_SHORTCUTS, id="help-panel"),
                Container(
                    Label("App", classes="dash-card-title"),
                    Label(f"Name: {Config.app_name()}", classes="dash-label"),
                    Label(f"Version: {Config.app_version()}", classes="dash-label"),
                    classes="settings-card",
                ),
                Container(
                    Label("Registered Tools", classes="dash-card-title"),
                    *[Label(f"  - {t['name']}  ({t['script']})", classes="dash-label") for t in Config.tools()],
                    classes="settings-card",
                ),
                Container(
                    Label("Python", classes="dash-card-title"),
                    Label(f"Version: {python_version()}", classes="dash-label"),
                    Label(f"Executable: {sys.executable}", classes="dash-label"),
                    classes="settings-card",
                ),
                classes="settings-content",
            ),
            classes="main-row",
        )
        yield Footer(classes="app-footer")

    def action_back(self) -> None:
        self.app.pop_screen()