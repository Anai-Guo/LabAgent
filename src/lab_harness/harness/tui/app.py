"""Terminal UI for LabAgent for Lab.

A Claude Code-style terminal interface for AI-guided lab automation.
"""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, RichLog, Static

from lab_harness.config import Settings
from lab_harness.harness.engine.context import RuntimeContext
from lab_harness.harness.engine.events import (
    ErrorEvent,
    SafetyCheck,
    StatusUpdate,
    TextDelta,
    ToolComplete,
    ToolStart,
    TurnComplete,
)
from lab_harness.harness.engine.query import run_query
from lab_harness.harness.engine.session import Session
from lab_harness.harness.tools.base import create_default_registry


class StatusBar(Static):
    """Bottom status bar showing system state."""

    def __init__(self):
        super().__init__("")
        self.model = "not configured"
        self.visa = "unknown"
        self.memory_count = 0
        self.budget = "0/50"

    def update_status(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.update(
            f" \u25cf Model: [bold cyan]{self.model}[/] "
            f" \u2502 VISA: [bold {'green' if self.visa == 'ok' else 'red'}]{self.visa}[/] "
            f" \u2502 Memory: [bold yellow]{self.memory_count}[/] "
            f" \u2502 Budget: [bold]{self.budget}[/] "
        )


class ConversationLog(RichLog):
    """Scrollable conversation display with rich formatting."""

    pass


class LabHarnessApp(App):
    """LabAgent for Lab -- Terminal Panel."""

    TITLE = "LabAgent for Lab"
    SUB_TITLE = "Fully Automated Lab Assistant"
    CSS = """
    Screen {
        background: #0f0f1e;
    }
    #conversation {
        height: 1fr;
        border: solid #2a2a55;
        background: #0d0d1a;
        padding: 1;
    }
    #input-area {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    #input-field {
        background: #1a1a3a;
        border: solid #c8a96e;
        color: #ece5d8;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: #131328;
        color: #a09a8d;
    }
    .tool-call {
        color: #c882ff;
    }
    .tool-result {
        color: #7bc639;
    }
    .safety-allow {
        color: #22c55e;
    }
    .safety-warn {
        color: #f0b232;
    }
    .safety-block {
        color: #ff6b4a;
    }
    .error {
        color: #ff6b4a;
    }
    .assistant {
        color: #ece5d8;
    }
    .user-msg {
        color: #4cc2ff;
    }
    """

    BINDINGS = [
        Binding("ctrl+m", "select_model", "Model"),
        Binding("ctrl+i", "scan_instruments", "Instruments"),
        Binding("ctrl+s", "save_session", "Save"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        self.session = Session.new(model=self.settings.model.model)
        self.registry = create_default_registry()
        self.context = RuntimeContext(
            tool_registry=self.registry,
            model_config=self.settings.model,
            session_id=self.session.session_id,
        )
        # Try to load memory store
        try:
            from lab_harness.memory.store import MemoryStore

            self.context.memory_store = MemoryStore()
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ConversationLog(id="conversation", wrap=True, highlight=True, markup=True)
        yield Input(placeholder="Type your message... (Ctrl+Q to quit)", id="input-field")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#conversation", ConversationLog)
        log.write(
            "[bold #c8a96e]\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557[/]"
        )
        log.write("[bold #c8a96e]\u2551   LabAgent for Lab -- Terminal     \u2551[/]")
        log.write("[bold #c8a96e]\u2551   Fully Automated Lab Assistant     \u2551[/]")
        log.write(
            "[bold #c8a96e]\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d[/]"
        )
        log.write("")
        log.write(f"[dim]Session: {self.session.session_id}[/]")
        log.write(f"[dim]Model: {self.settings.model.model}[/]")
        log.write(f"[dim]Tools: {', '.join(self.registry.list_tools())}[/]")
        log.write("")
        log.write("[#a09a8d]Type a message to begin. Examples:[/]")
        log.write("[#64748b]  \u2022 scan my instruments[/]")
        log.write("[#64748b]  \u2022 propose a Hall effect measurement[/]")
        log.write("[#64748b]  \u2022 analyze data.csv --type IV[/]")
        log.write("")

        self._update_status()

    def _update_status(self):
        status = self.query_one(StatusBar)
        status.update_status(
            model=self.settings.model.model.split("/")[-1]
            if "/" in self.settings.model.model
            else self.settings.model.model,
            budget=f"{self.context._turns_used}/{self.context.max_turns}",
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        input_widget = self.query_one("#input-field", Input)
        input_widget.value = ""

        log = self.query_one("#conversation", ConversationLog)
        log.write(f"\n[bold #4cc2ff]> {user_text}[/]\n")

        self.session.add_user_message(user_text)
        self.process_query(user_text)

    @work(exclusive=True)
    async def process_query(self, user_text: str) -> None:
        log = self.query_one("#conversation", ConversationLog)

        messages = [{"role": "user", "content": user_text}]

        assistant_text = ""
        try:
            async for event in run_query(self.context, messages):
                if isinstance(event, TextDelta):
                    assistant_text += event.text
                    # Show accumulated text
                    log.write(f"[#ece5d8]{event.text}[/]", scroll_end=True)

                elif isinstance(event, ToolStart):
                    log.write(
                        f"\n[bold #c882ff]\u26a1 {event.tool_name}[/] [dim]{event.tool_input}[/]",
                        scroll_end=True,
                    )

                elif isinstance(event, ToolComplete):
                    color = "#7bc639" if not event.is_error else "#ff6b4a"
                    symbol = "\u2713" if not event.is_error else "\u2717"
                    # Truncate long output
                    output = event.output[:200] + "..." if len(event.output) > 200 else event.output
                    log.write(f"[{color}]  {symbol} {output}[/]\n", scroll_end=True)

                elif isinstance(event, SafetyCheck):
                    colors = {"allow": "#22c55e", "require_confirm": "#f0b232", "block": "#ff6b4a"}
                    color = colors.get(event.decision, "#a09a8d")
                    log.write(
                        f"\n[bold {color}]Safety: {event.decision.upper()}[/]",
                        scroll_end=True,
                    )
                    log.write(f"[{color}]  {event.message}[/]\n", scroll_end=True)

                elif isinstance(event, StatusUpdate):
                    self._update_status()

                elif isinstance(event, ErrorEvent):
                    log.write(f"\n[bold #ff6b4a]Error: {event.message}[/]\n", scroll_end=True)

                elif isinstance(event, TurnComplete):
                    if event.text and event.text != assistant_text:
                        log.write(f"[#ece5d8]{event.text}[/]", scroll_end=True)
                    self._update_status()

        except Exception as e:
            log.write(f"\n[bold red]Exception: {e}[/]\n", scroll_end=True)

        if assistant_text:
            self.session.add_assistant_message(assistant_text)

    def action_select_model(self) -> None:
        log = self.query_one("#conversation", ConversationLog)
        log.write("\n[bold #c8a96e]Model selection: Edit configs/models.yaml and restart[/]\n")

    def action_scan_instruments(self) -> None:
        self.process_query("scan my instruments")

    def action_save_session(self) -> None:
        from pathlib import Path

        path = Path(f"data/sessions/{self.session.session_id}.json")
        self.session.save(path)
        log = self.query_one("#conversation", ConversationLog)
        log.write(f"\n[#22c55e]Session saved to {path}[/]\n")


def run_panel(model: str | None = None):
    """Launch the terminal panel."""
    app = LabHarnessApp()
    if model:
        app.settings = Settings.load()
        # Override model if specified
    app.run()
