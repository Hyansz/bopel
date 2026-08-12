"""Reusable panel widgets — info cards, log panels, help panel."""

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, RichLog


class InfoPanel(Widget):
    """A titled card with key-value pairs."""

    DEFAULT_CSS = """
    InfoPanel {
        height: auto;
        padding: 1 2;
        background: #1e1e2e;
        border: round #313244;
    }
    .info-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }
    .info-row { height: 1; }
    .info-key { color: #a6adc8; }
    .info-val { color: #cdd6f4; text-style: bold; }
    """

    def __init__(self, title: str, rows: list[tuple[str, str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._rows = rows

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="info-title")
        for key, val in self._rows:
            yield Label(
                Text.assemble((f"{key}: ", "info-key"), (val, "info-val")),
                classes="info-row",
            )


class LogPanel(Widget):
    """A titled RichLog wrapper."""

    DEFAULT_CSS = """
    LogPanel {
        height: 1fr;
    }
    .log-title {
        text-style: bold;
        color: #89b4fa;
        padding: 0 0 0 1;
    }
    .log-box {
        height: 1fr;
        background: #11111b;
        border: round #313244;
    }
    """

    def __init__(self, title: str = "Output", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="log-title")
        yield RichLog(classes="log-box", highlight=True, markup=True, auto_scroll=True)

    def write(self, text: str) -> None:
        self.query_one(".log-box", RichLog).write(text)

    def clear(self) -> None:
        self.query_one(".log-box", RichLog).clear()


class HelpPanel(Widget):
    """Toggleable shortcut reference panel. Hidden by default; add class
    '-visible' to show. Toggled with the '?' key (see HelpMixin in dashboard.py).
    """

    DEFAULT_CSS = """
    HelpPanel {
        display: none;
        background: #181825;
        border: round #f9e2af;
        padding: 1 2;
        margin: 1 0 0 0;
        height: auto;
    }
    HelpPanel.-visible {
        display: block;
    }
    .help-title { color: #f9e2af; text-style: bold; margin-bottom: 1; }
    .help-row { color: #a6adc8; height: 1; }
    """

    def __init__(self, shortcuts: list[tuple[str, str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._shortcuts = shortcuts

    def compose(self) -> ComposeResult:
        yield Label("Panel bantuan  (tekan ? untuk tutup)", classes="help-title")
        for key, desc in self._shortcuts:
            yield Label(f"[cyan]{key:<12}[/cyan] {desc}", classes="help-row", markup=True)