"""Sidebar widget — VS Code-style left panel with menu buttons."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label

from core.config import Config


class MenuSelected(Message):
    """Emitted when a sidebar menu item is activated."""

    def __init__(self, tool_name: str, script_name: str = "", action: str = "") -> None:
        super().__init__()
        self.tool_name = tool_name
        self.script_name = script_name
        self.action = action


def _safe_id(script: str) -> str:
    """Turn a script filename like 'check.py' into a valid Textual widget id."""
    return "tool-" + script.replace(".", "-").replace(" ", "-")


class Sidebar(Widget):
    """Left-hand sidebar with navigation buttons built from config.yaml."""

    BINDINGS = [
        Binding("up", "sidebar_prev", show=False, priority=True),
        Binding("down", "sidebar_next", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    Sidebar {
        width: 30;
        height: 1fr;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # maps sanitized widget id -> real script filename
        self._id_to_script: dict[str, str] = {}

    def action_sidebar_prev(self) -> None:
        self._cycle_focus(-1)

    def action_sidebar_next(self) -> None:
        self._cycle_focus(1)

    def _cycle_focus(self, direction: int) -> None:
        btns = list(self.query(".menu-btn"))
        if not btns:
            return
        focused_idx = -1
        for i, btn in enumerate(btns):
            if btn.has_focus:
                focused_idx = i
                break
        if focused_idx == -1:
            btns[0].focus()
        elif direction == 1:
            btns[(focused_idx + 1) % len(btns)].focus()
        else:
            btns[(focused_idx - 1) % len(btns)].focus()

    def compose(self) -> ComposeResult:
        yield Label("BOPEL AUTOMATION", classes="sidebar-title")
        yield Label(Config.app_subtitle(), classes="sidebar-subtitle")

        yield Label("TOOLS", classes="sidebar-section")
        for tool_cfg in Config.tools():
            name = tool_cfg.get("name", "Unnamed")
            script = tool_cfg["script"]
            widget_id = _safe_id(script)
            self._id_to_script[widget_id] = script
            yield Button(name, id=widget_id, classes="menu-btn")

        yield Label("GENERAL", classes="sidebar-section")
        yield Button("\U0001f4dc  Logs", id="nav-logs", classes="menu-btn")
        yield Button("\u2699\ufe0f  Settings", id="nav-settings", classes="menu-btn")
        yield Button("\U0001f6aa  Exit", id="nav-exit", classes="menu-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        for btn in self.query(".menu-btn"):
            btn.remove_class("-active")
        event.button.add_class("-active")

        if btn_id in self._id_to_script:
            script = self._id_to_script[btn_id]
            tool_cfg = next((t for t in Config.tools() if t["script"] == script), {})
            self.post_message(MenuSelected(
                tool_name=tool_cfg.get("name", script),
                script_name=script,
            ))
        elif btn_id == "nav-logs":
            self.post_message(MenuSelected(tool_name="Logs", action="logs"))
        elif btn_id == "nav-settings":
            self.post_message(MenuSelected(tool_name="Settings", action="settings"))
        elif btn_id == "nav-exit":
            self.app.exit()