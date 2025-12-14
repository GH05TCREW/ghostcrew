"""
GhostCrew TUI - Terminal User Interface
"""

import asyncio
import textwrap
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Center,
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.scrollbar import ScrollBar, ScrollBarRender
from textual.timer import Timer
from textual.widgets import Button, Input, Static, Tree
from textual.widgets.tree import TreeNode

from ..config.constants import DEFAULT_MODEL


# ASCII-safe scrollbar renderer to avoid Unicode glyph issues
class ASCIIScrollBarRender(ScrollBarRender):
    """Scrollbar renderer using ASCII-safe characters."""

    BLANK_GLYPH = " "
    VERTICAL_BARS = [" ", " ", " ", " ", " ", " ", " ", " "]
    HORIZONTAL_BARS = [" ", " ", " ", " ", " ", " ", " ", " "]


# Apply ASCII scrollbar globally
ScrollBar.renderer = ASCIIScrollBarRender


# Custom Tree with ASCII-safe icons for PowerShell compatibility
class CrewTree(Tree):
    """Tree widget with ASCII-compatible expand/collapse icons."""

    ICON_NODE = "> "
    ICON_NODE_EXPANDED = "v "


if TYPE_CHECKING:
    from ..agents.ghostcrew_agent import GhostCrewAgent


def wrap_text_lines(text: str, width: int = 80) -> List[str]:
    """
    Wrap text content preserving line breaks and wrapping long lines.

    Args:
        text: The text to wrap
        width: Maximum width per line (default 80 for safe terminal fit)

    Returns:
        List of wrapped lines
    """
    result = []
    for line in text.split("\n"):
        if len(line) <= width:
            result.append(line)
        else:
            # Wrap long lines
            wrapped = textwrap.wrap(
                line, width=width, break_long_words=False, break_on_hyphens=False
            )
            result.extend(wrapped if wrapped else [""])
    return result


# ----- Help Screen -----


class HelpScreen(ModalScreen):
    """Help modal"""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    CSS = """
    HelpScreen {
        align: center middle;
        scrollbar-background: #1a1a1a;
        scrollbar-background-hover: #1a1a1a;
        scrollbar-background-active: #1a1a1a;
        scrollbar-color: #3a3a3a;
        scrollbar-color-hover: #3a3a3a;
        scrollbar-color-active: #3a3a3a;
        scrollbar-corner-color: #1a1a1a;
        scrollbar-size: 1 1;
    }

    #help-container {
        width: 60;
        height: 23;
        background: #121212;
        border: solid #3a3a3a;
        padding: 1 2;
    }

    #help-title {
        text-align: center;
        text-style: bold;
        color: #d4d4d4;
        margin-bottom: 1;
    }

    #help-content {
        color: #9a9a9a;
    }

    #help-close {
        margin-top: 1;
        width: auto;
        min-width: 10;
        background: #1a1a1a;
        color: #9a9a9a;
        border: none;
    }

    #help-close:hover {
        background: #262626;
    }

    #help-close:focus {
        background: #262626;
        text-style: none;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Static("GhostCrew Help", id="help-title"),
            Static(self._get_help_text(), id="help-content"),
            Center(Button("Close", id="help-close")),
            id="help-container",
        )

    def _get_help_text(self) -> str:
        return """[bold]Modes:[/] Assist | Agent | Crew
[bold]Keys:[/] Enter=Send  Ctrl+C=Stop  Ctrl+Q=Quit  F1=Help

[bold]Commands:[/]
  /agent <task>         - Run in agent mode
  /crew <task>          - Run multi-agent crew mode
  /target <host>        - Set target
  /prompt               - Show system prompt
  /memory               - Show memory stats
  /notes                - Show saved notes
  /report               - Generate report
  /help                 - Show help
  /clear                - Clear chat
  /tools                - List tools
  /quit                 - Exit"""

    def action_dismiss(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#help-close")
    def close_help(self) -> None:
        self.app.pop_screen()


# ----- Main Chat Message Widgets -----


class ThinkingMessage(Static):
    """Thinking/reasoning message"""

    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self.thinking_content = content

    def render(self) -> Text:
        text = Text()
        text.append("| ", style="#3a3a3a")
        text.append("* ", style="#9a9a9a")
        text.append("Thinking\n", style="bold #9a9a9a")

        # Wrap content - use 70 chars to account for sidebar + prefix
        for line in wrap_text_lines(self.thinking_content, width=70):
            text.append("|   ", style="#3a3a3a")
            text.append(f"{line}\n", style="#6b6b6b italic")

        return text


class ToolMessage(Static):
    """Tool execution message"""

    # Standard tool icon and color (ghost theme)
    TOOL_ICON = "$"
    TOOL_COLOR = "#9a9a9a"  # spirit gray

    def __init__(self, tool_name: str, args: str = "", **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.tool_args = args

    def render(self) -> Text:
        text = Text()
        text.append("| ", style="#3a3a3a")
        text.append(f"{self.TOOL_ICON} ", style=self.TOOL_COLOR)
        text.append(f"{self.tool_name}", style=self.TOOL_COLOR)
        text.append("\n", style="")

        # Wrap args and show each line with vertical bar
        if self.tool_args:
            for line in wrap_text_lines(self.tool_args, width=100):
                text.append("|   ", style="#3a3a3a")
                text.append(f"{line}\n", style="#6b6b6b")

        return text


class ToolResultMessage(Static):
    """Tool result/output message"""

    RESULT_ICON = "#"
    RESULT_COLOR = "#7a7a7a"

    def __init__(self, tool_name: str, result: str = "", **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.result = result

    def render(self) -> Text:
        text = Text()
        text.append("| ", style="#3a3a3a")
        text.append(f"{self.RESULT_ICON} ", style=self.RESULT_COLOR)
        text.append(f"{self.tool_name} output", style=self.RESULT_COLOR)
        text.append("\n", style="")

        if self.result:
            for line in wrap_text_lines(self.result, width=100):
                text.append("|   ", style="#3a3a3a")
                text.append(f"{line}\n", style="#5a5a5a")

        return text


class AssistantMessage(Static):
    """Assistant response message"""

    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self.message_content = content

    def render(self) -> Text:
        text = Text()
        text.append("| ", style="#525252")
        text.append(">> ", style="#9a9a9a")
        text.append("Ghost\n", style="bold #d4d4d4")

        # Wrap content - use 70 chars to account for sidebar + prefix
        for line in wrap_text_lines(self.message_content, width=70):
            text.append("|   ", style="#525252")
            text.append(f"{line}\n", style="#d4d4d4")

        return text


class UserMessage(Static):
    """User message"""

    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self.message_content = content

    def render(self) -> Text:
        text = Text()
        text.append("| ", style="#6b6b6b")  # phantom border
        text.append("> ", style="#9a9a9a")
        text.append("You\n", style="bold #d4d4d4")  # specter
        text.append("|   ", style="#6b6b6b")  # phantom border
        text.append(f"{self.message_content}\n", style="#d4d4d4")  # specter
        return text


class SystemMessage(Static):
    """System message"""

    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self.message_content = content

    def render(self) -> Text:
        text = Text()
        for line in self.message_content.split("\n"):
            text.append(f"  {line}\n", style="#6b6b6b")  # phantom - subtle system text
        return text


# ----- Status Bar -----


class StatusBar(Static):
    """Animated status bar"""

    status = reactive("idle")
    mode = reactive("assist")  # "assist" or "agent"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frame = 0
        self._timer: Optional[Timer] = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.2, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % 4
        if self.status not in ["idle", "complete"]:
            self.refresh()

    def render(self) -> Text:
        dots = "." * (self._frame + 1)

        # Use fixed-width labels (pad dots to 4 chars so text doesn't jump)
        dots_padded = dots.ljust(4)

        # Ghost theme status colors (muted, ethereal)
        status_map = {
            "idle": ("Ready", "#6b6b6b"),
            "initializing": (f"Initializing{dots_padded}", "#9a9a9a"),
            "thinking": (f"Thinking{dots_padded}", "#9a9a9a"),
            "running": (f"Running{dots_padded}", "#9a9a9a"),
            "processing": (f"Processing{dots_padded}", "#9a9a9a"),
            "waiting": ("Waiting for input", "#9a9a9a"),
            "complete": ("Complete", "#4a9f6e"),
            "error": ("Error", "#9f4a4a"),
        }

        label, color = status_map.get(self.status, (self.status, "#6b6b6b"))

        text = Text()

        # Show mode (ASCII-safe symbols)
        if self.mode == "crew":
            text.append("  :: Crew ", style="#9a9a9a")
        elif self.mode == "agent":
            text.append("  >> Agent ", style="#9a9a9a")
        else:
            text.append("  >> Assist ", style="#9a9a9a")

        text.append(f"| {label}", style=color)

        if self.status not in ["idle", "initializing", "complete", "error"]:
            text.append("    ESC to stop", style="#525252")

        return text


# ----- Main TUI App -----


class GhostCrewTUI(App):
    """Main GhostCrew TUI Application"""

    # ═══════════════════════════════════════════════════════════
    # GHOST THEME - Ethereal grays emerging from darkness
    # ═══════════════════════════════════════════════════════════
    # Void:       #0a0a0a  (terminal black - the darkness)
    # Shadow:     #121212  (subtle surface)
    # Mist:       #1a1a1a  (panels, elevated)
    # Whisper:    #262626  (default borders)
    # Fog:        #3a3a3a  (hover states)
    # Apparition: #525252  (focus states)
    # Phantom:    #6b6b6b  (secondary text)
    # Spirit:     #9a9a9a  (normal text)
    # Specter:    #d4d4d4  (primary text)
    # Ectoplasm:  #f0f0f0  (highlights)
    # ═══════════════════════════════════════════════════════════

    CSS = """
    Screen {
        background: #0a0a0a;
    }

    #main-container {
        width: 100%;
        height: 100%;
        layout: horizontal;
    }

    /* Chat area - takes full width normally, fills remaining space with sidebar */
    #chat-area {
        width: 1fr;
        height: 100%;
    }

    #chat-area.with-sidebar {
        width: 1fr;
    }

    #chat-scroll {
        width: 100%;
        height: 1fr;
        background: transparent;
        padding: 1 2;
        scrollbar-background: #1a1a1a;
        scrollbar-background-hover: #1a1a1a;
        scrollbar-background-active: #1a1a1a;
        scrollbar-color: #3a3a3a;
        scrollbar-color-hover: #3a3a3a;
        scrollbar-color-active: #3a3a3a;
        scrollbar-corner-color: #1a1a1a;
        scrollbar-size: 1 1;
    }

    #input-container {
        width: 100%;
        height: 3;
        background: transparent;
        border: round #262626;
        margin: 0 2;
        padding: 0;
        layout: horizontal;
        align-vertical: middle;
    }

    #input-container:focus-within {
        border: round #525252;
    }

    #input-container:focus-within #chat-prompt {
        color: #d4d4d4;
    }

    #chat-prompt {
        width: auto;
        height: 100%;
        padding: 0 0 0 1;
        color: #6b6b6b;
        content-align-vertical: middle;
    }

    #chat-input {
        width: 1fr;
        height: 100%;
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
        color: #d4d4d4;
    }

    #chat-input:focus {
        border: none;
    }

    #chat-input > .input--placeholder {
        color: #6b6b6b;
        text-style: italic;
    }

    #status-bar {
        width: 100%;
        height: 1;
        background: transparent;
        padding: 0 3;
        margin: 0;
    }

    .message {
        margin-bottom: 1;
    }

    /* Sidebar - hidden by default */
    #sidebar {
        width: 28;
        height: 100%;
        display: none;
        padding-right: 1;
    }

    #sidebar.visible {
        display: block;
    }

    #workers-tree {
        height: 1fr;
        background: transparent;
        border: round #262626;
        padding: 0 1;
        margin-bottom: 0;
    }

    #workers-tree:focus {
        border: round #3a3a3a;
    }

    #crew-stats {
        height: auto;
        max-height: 10;
        background: transparent;
        border: round #262626;
        border-title-color: #9a9a9a;
        border-title-style: bold;
        padding: 0 1;
        margin-top: 0;
    }

    Tree {
        background: transparent;
        color: #d4d4d4;
        scrollbar-background: #1a1a1a;
        scrollbar-background-hover: #1a1a1a;
        scrollbar-background-active: #1a1a1a;
        scrollbar-color: #3a3a3a;
        scrollbar-color-hover: #3a3a3a;
        scrollbar-color-active: #3a3a3a;
        scrollbar-size: 1 1;
    }

    Tree > .tree--cursor {
        background: transparent;
    }

    Tree > .tree--highlight {
        background: transparent;
    }

    Tree > .tree--highlight-line {
        background: transparent;
    }

    .tree--node-label {
        padding: 0 1;
    }

    .tree--node:hover .tree--node-label {
        background: transparent;
    }

    .tree--node.-selected .tree--node-label {
        background: transparent;
        color: #d4d4d4;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit_app", "Quit", priority=True),
        Binding("ctrl+c", "stop_agent", "Stop", priority=True, show=False),
        Binding("escape", "stop_agent", "Stop", priority=True),
        Binding("f1", "show_help", "Help"),
        Binding("tab", "focus_next", "Next", show=False),
    ]

    TITLE = "GhostCrew"
    SUB_TITLE = "AI Penetration Testing"

    def __init__(
        self,
        target: Optional[str] = None,
        model: str = None,
        use_docker: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.target = target
        self.model = model or DEFAULT_MODEL
        self.use_docker = use_docker

        # Agent components
        self.agent: Optional["GhostCrewAgent"] = None
        self.runtime = None
        self.mcp_manager = None
        self.all_tools = []
        self.rag_engine = None  # RAG engine

        # State
        self._mode = "assist"  # "assist", "agent", or "crew"
        self._is_running = False
        self._is_initializing = True  # Block input during init
        self._should_stop = False
        self._current_worker = None  # Track running worker for cancellation
        self._current_crew = None  # Track crew orchestrator for cancellation

        # Crew mode state
        self._crew_workers: Dict[str, Dict[str, Any]] = {}
        self._crew_worker_nodes: Dict[str, TreeNode] = {}
        self._crew_orchestrator_node: Optional[TreeNode] = None
        self._crew_findings_count = 0
        self._viewing_worker_id: Optional[str] = None
        self._worker_events: Dict[str, List[Dict]] = {}
        self._crew_start_time: Optional[float] = None
        self._crew_tokens_used: int = 0
        self._crew_stats_timer: Optional[Timer] = None
        self._spinner_timer: Optional[Timer] = None
        self._spinner_frame: int = 0
        self._spinner_frames = [
            "⠋",
            "⠙",
            "⠹",
            "⠸",
            "⠼",
            "⠴",
            "⠦",
            "⠧",
            "⠇",
            "⠏",
        ]  # Braille dots spinner

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-container"):
            # Chat area (left side)
            with Vertical(id="chat-area"):
                yield ScrollableContainer(id="chat-scroll")
                yield StatusBar(id="status-bar")
                with Horizontal(id="input-container"):
                    yield Static("> ", id="chat-prompt")
                    yield Input(placeholder="Enter task or type /help", id="chat-input")

            # Sidebar (right side, hidden by default)
            with Vertical(id="sidebar"):
                yield CrewTree("CREW", id="workers-tree")
                yield Static("", id="crew-stats")

    async def on_mount(self) -> None:
        """Initialize on mount"""
        self._initialize_agent()

    @work(thread=False)
    async def _initialize_agent(self) -> None:
        """Initialize agent"""
        self._set_status("initializing")

        try:
            import os

            from ..agents.ghostcrew_agent import GhostCrewAgent
            from ..knowledge import RAGEngine
            from ..llm import LLM, ModelConfig
            from ..mcp import MCPManager
            from ..runtime.docker_runtime import DockerRuntime
            from ..runtime.runtime import LocalRuntime
            from ..tools import get_all_tools, register_tool_instance

            # RAG Engine - auto-load knowledge sources
            rag_doc_count = 0
            knowledge_path = None

            # Check local knowledge dir first (must have files, not just exist)
            local_knowledge = Path("knowledge")
            bundled_path = Path(__file__).parent.parent / "knowledge" / "sources"

            if local_knowledge.exists() and any(local_knowledge.rglob("*.*")):
                knowledge_path = local_knowledge
            elif bundled_path.exists():
                knowledge_path = bundled_path

            if knowledge_path:
                try:
                    # Determine embedding method: env var > auto-detect
                    embeddings_setting = os.getenv("GHOSTCREW_EMBEDDINGS", "").lower()
                    if embeddings_setting == "local":
                        use_local = True
                    elif embeddings_setting == "openai":
                        use_local = False
                    else:
                        # Auto: use OpenAI if key available, else local
                        use_local = not os.getenv("OPENAI_API_KEY")

                    self.rag_engine = RAGEngine(
                        knowledge_path=knowledge_path, use_local_embeddings=use_local
                    )
                    await asyncio.to_thread(self.rag_engine.index)
                    rag_doc_count = self.rag_engine.get_document_count()
                except Exception as e:
                    self._add_system(f"[!] RAG: {e}")
                    self.rag_engine = None

            # MCP - auto-load if config exists
            mcp_server_count = 0
            try:
                self.mcp_manager = MCPManager()
                if self.mcp_manager.config_path.exists():
                    mcp_tools = await self.mcp_manager.connect_all()
                    for tool in mcp_tools:
                        register_tool_instance(tool)
                    mcp_server_count = len(self.mcp_manager.servers)
            except Exception as e:
                self._add_system(f"[!] MCP: {e}")

            # Runtime - Docker or Local
            if self.use_docker:
                self._add_system("+ Starting Docker container...")
                self.runtime = DockerRuntime(mcp_manager=self.mcp_manager)
            else:
                self.runtime = LocalRuntime(mcp_manager=self.mcp_manager)
            await self.runtime.start()

            # LLM
            llm = LLM(
                model=self.model,
                config=ModelConfig(temperature=0.7),
                rag_engine=self.rag_engine,
            )

            # Tools
            self.all_tools = get_all_tools()

            # Agent
            self.agent = GhostCrewAgent(
                llm=llm,
                tools=self.all_tools,
                runtime=self.runtime,
                target=self.target,
                rag_engine=self.rag_engine,
            )

            self._set_status("idle", "assist")
            self._is_initializing = False  # Allow input now

            # Show ready message
            tools_str = ", ".join(t.name for t in self.all_tools[:5])
            if len(self.all_tools) > 5:
                tools_str += f", +{len(self.all_tools) - 5} more"

            runtime_str = "Docker" if self.use_docker else "Local"
            self._add_system(
                f"+ GhostCrew ready\n"
                f"  Model: {self.model} | Tools: {len(self.all_tools)} | MCP: {mcp_server_count} | RAG: {rag_doc_count}\n"
                f"  Runtime: {runtime_str} | Mode: Assist (use /agent or /crew for autonomous modes)"
            )

            # Show target if provided (but don't auto-start)
            if self.target:
                self._add_system(f"  Target: {self.target}")

        except Exception as e:
            import traceback

            self._add_system(f"[!] Init failed: {e}\n{traceback.format_exc()}")
            self._set_status("error")
            self._is_initializing = False  # Allow input even on error

    def _set_status(self, status: str, mode: Optional[str] = None) -> None:
        """Update status bar"""
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.status = status
            if mode:
                bar.mode = mode
                self._mode = mode
        except Exception:
            pass

    def _add_message(self, widget: Static) -> None:
        """Add a message widget to chat"""
        try:
            scroll = self.query_one("#chat-scroll", ScrollableContainer)
            widget.add_class("message")
            scroll.mount(widget)
            scroll.scroll_end(animate=False)
        except Exception:
            pass

    def _add_system(self, content: str) -> None:
        self._add_message(SystemMessage(content))

    def _add_user(self, content: str) -> None:
        self._add_message(UserMessage(content))

    def _add_assistant(self, content: str) -> None:
        self._add_message(AssistantMessage(content))

    def _add_thinking(self, content: str) -> None:
        self._add_message(ThinkingMessage(content))

    def _add_tool(self, name: str, action: str = "") -> None:
        self._add_message(ToolMessage(name, action))

    def _add_tool_result(self, name: str, result: str) -> None:
        """Display tool execution result"""
        # Hide tool output - LLM will synthesize it in its response
        # This prevents duplication and keeps the chat clean
        pass

    def _show_system_prompt(self) -> None:
        """Display the current system prompt"""
        if self.agent:
            prompt = self.agent.get_system_prompt()
            self._add_system(f"=== System Prompt ===\n{prompt}")
        else:
            self._add_system("Agent not initialized")

    def _show_memory_stats(self) -> None:
        """Display memory usage statistics"""
        if self.agent and self.agent.llm:
            stats = self.agent.llm.get_memory_stats()
            messages_count = len(self.agent.conversation_history)

            # Format messages for token counting
            llm_messages = self.agent._format_messages_for_llm()
            current_tokens = self.agent.llm.memory.get_total_tokens(llm_messages)

            info = (
                f"=== Memory Stats ===\n"
                f"Messages: {messages_count}\n"
                f"Current tokens: {current_tokens:,}\n"
                f"Token budget: {stats['token_budget']:,}\n"
                f"Summarize at: {stats['summarize_threshold']:,} tokens\n"
                f"Recent to keep: {stats['recent_to_keep']} messages\n"
                f"Has summary: {stats['has_summary']}\n"
                f"Summarized: {stats['summarized_message_count']} messages"
            )
            self._add_system(info)
        else:
            self._add_system("Agent not initialized")

    async def _show_notes(self) -> None:
        """Display saved notes"""
        from ..tools.notes import get_all_notes

        notes = await get_all_notes()
        if not notes:
            self._add_system(
                "=== Notes ===\nNo notes saved.\n\nThe AI can save key findings using the notes tool."
            )
            return

        lines = [f"=== Notes ({len(notes)} entries) ==="]
        for key, value in notes.items():
            # Show full value, indent multi-line content
            if "\n" in value:
                indented = value.replace("\n", "\n    ")
                lines.append(f"\n[{key}]\n    {indented}")
            else:
                lines.append(f"[{key}] {value}")
        lines.append("\nFile: loot/notes.json")
        lines.append("Reports: loot/reports/")

        self._add_system("\n".join(lines))

    def _build_prior_context(self) -> str:
        """Build a summary of prior findings for crew mode.

        Extracts:
        - Tool results (nmap scans, etc.) - the actual findings
        - Assistant analyses - interpretations and summaries
        - Last user task - what they were working on

        Excludes:
        - Raw user messages (noise)
        - Tool call declarations (just names/args, not results)
        - Very short responses
        """
        if not self.agent or not self.agent.conversation_history:
            return ""

        findings = []
        last_user_task = ""

        for msg in self.agent.conversation_history:
            # Track user tasks/questions
            if msg.role == "user" and msg.content:
                last_user_task = msg.content[:200]

            # Extract tool results (the actual findings)
            elif msg.tool_results:
                for result in msg.tool_results:
                    if result.success and result.result:
                        content = (
                            result.result[:1500]
                            if len(result.result) > 1500
                            else result.result
                        )
                        findings.append(f"[{result.tool_name}]\n{content}")

            # Include assistant analyses (but not tool call messages)
            elif msg.role == "assistant" and msg.content and not msg.tool_calls:
                if len(msg.content) > 50:
                    findings.append(f"[Analysis]\n{msg.content[:1000]}")

        if not findings and not last_user_task:
            return ""

        # Build context with last user task + recent findings
        parts = []
        if last_user_task:
            parts.append(f"Last task: {last_user_task}")
        if findings:
            parts.append("Findings:\n" + "\n\n".join(findings[-5:]))

        context = "\n\n".join(parts)
        if len(context) > 4000:
            context = context[:4000] + "\n... (truncated)"

        return context

    def _set_target(self, cmd: str) -> None:
        """Set the target for the engagement"""
        # Remove /target prefix
        target = cmd[7:].strip()

        if not target:
            if self.target:
                self._add_system(
                    f"Current target: {self.target}\nUsage: /target <host>"
                )
            else:
                self._add_system(
                    "No target set.\nUsage: /target <host>\nExample: /target 192.168.1.1"
                )
            return

        self.target = target

        # Update agent's target if agent exists
        if self.agent:
            self.agent.target = target

        self._add_system(f"@ Target set: {target}")

    @work(exclusive=True)
    async def _run_report_generation(self) -> None:
        """Generate a pentest report from notes and conversation"""
        from pathlib import Path

        from ..tools.notes import get_all_notes

        if not self.agent or not self.agent.llm:
            self._add_system("[!] Agent not initialized")
            return

        notes = await get_all_notes()
        if not notes:
            self._add_system(
                "No notes found. Ghost saves findings using the notes tool during testing."
            )
            return

        self._add_system("Generating report...")

        # Format notes
        notes_text = "\n".join(f"### {k}\n{v}\n" for k, v in notes.items())

        # Build conversation summary from full history
        conversation_summary = ""
        if self.agent.conversation_history:
            # Summarize key actions from conversation
            actions = []
            for msg in self.agent.conversation_history:
                if msg.role == "assistant" and msg.tool_calls:
                    for tc in msg.tool_calls:
                        actions.append(f"- Tool: {tc.name}")
                elif msg.role == "tool_result" and msg.tool_results:
                    for tr in msg.tool_results:
                        # Include truncated result
                        result = tr.result or ""
                        output = result[:200] + "..." if len(result) > 200 else result
                        actions.append(f"  Result: {output}")
            if actions:
                conversation_summary = "\n".join(actions[-30:])  # Last 30 actions

        report_prompt = f"""Generate a penetration test report in Markdown from the notes below.

# Notes
{notes_text}

# Activity Log
{conversation_summary if conversation_summary else "N/A"}

# Target
{self.target or "Not specified"}

Output a report with:
1. Executive Summary (2-3 sentences)
2. Findings (use notes, include severity: Critical/High/Medium/Low/Info)
3. Recommendations

Be concise. Use the actual data from notes."""

        try:
            report_content = await self.agent.llm.simple_completion(
                prompt=report_prompt,
                system="You are a penetration tester writing a security report. Be concise and factual.",
            )

            if not report_content or not report_content.strip():
                self._add_system(
                    "[!] Report generation returned empty. Check LLM connection."
                )
                return

            # Save to loot/reports/
            reports_dir = Path("loot/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)

            # Append Shadow Graph if available
            try:
                from ..knowledge.graph import ShadowGraph
                from ..tools.notes import get_all_notes_sync

                # Rehydrate graph from notes
                graph = ShadowGraph()
                notes = get_all_notes_sync()
                if notes:
                    graph.update_from_notes(notes)
                    mermaid_code = graph.to_mermaid()

                    if mermaid_code:
                        report_content += (
                            "\n\n## Attack Graph (Visual)\n\n```mermaid\n"
                            + mermaid_code
                            + "\n```\n"
                        )
            except Exception as e:
                self._add_system(f"[!] Graph generation error: {e}")

            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            report_path = reports_dir / f"report_{timestamp}.md"
            report_path.write_text(report_content, encoding="utf-8")

            self._add_system(f"+ Report saved: {report_path}")

        except Exception as e:
            self._add_system(f"[!] Report error: {e}")

    @on(Input.Submitted, "#chat-input")
    async def handle_submit(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        # Block input while initializing or AI is processing
        if self._is_initializing or self._is_running:
            return

        message = event.value.strip()
        if not message:
            return

        event.input.value = ""

        # Commands
        if message.startswith("/"):
            await self._handle_command(message)
            return

        self._add_user(message)

        # Hide crew sidebar when entering assist mode
        self._hide_sidebar()

        # Use assist mode by default
        if self.agent and not self._is_running:
            self._current_worker = self._run_assist(message)

    async def _handle_command(self, cmd: str) -> None:
        """Handle slash commands"""
        cmd_lower = cmd.lower().strip()
        cmd_original = cmd.strip()

        if cmd_lower in ["/help", "/h", "/?"]:
            await self.push_screen(HelpScreen())
        elif cmd_lower == "/clear":
            scroll = self.query_one("#chat-scroll", ScrollableContainer)
            await scroll.remove_children()
            self._hide_sidebar()
            # Clear agent conversation history for fresh start
            if self.agent:
                self.agent.conversation_history.clear()
            self._add_system("Chat cleared")
        elif cmd_lower == "/tools":
            names = [t.name for t in self.all_tools]
            self._add_system(f"Tools ({len(names)}): " + ", ".join(names))
        elif cmd_lower in ["/quit", "/exit", "/q"]:
            self.exit()
        elif cmd_lower == "/prompt":
            self._show_system_prompt()
        elif cmd_lower == "/memory":
            self._show_memory_stats()
        elif cmd_lower == "/notes":
            await self._show_notes()
        elif cmd_lower == "/report":
            self._run_report_generation()
        elif cmd_original.startswith("/target"):
            self._set_target(cmd_original)
        elif cmd_original.startswith("/agent"):
            await self._parse_agent_command(cmd_original)
        elif cmd_original.startswith("/crew"):
            await self._parse_crew_command(cmd_original)
        else:
            self._add_system(f"Unknown command: {cmd}\nType /help for commands.")

    async def _parse_agent_command(self, cmd: str) -> None:
        """Parse and execute /agent command"""

        # Remove /agent prefix
        rest = cmd[6:].strip()

        if not rest:
            self._add_system(
                "Usage: /agent <task>\n"
                "Example: /agent scan 192.168.1.1\n"
                "         /agent enumerate SSH on target"
            )
            return

        task = rest

        if not task:
            self._add_system("Error: No task provided. Usage: /agent <task>")
            return

        self._add_user(f"/agent {task}")
        self._add_system(">> Agent Mode")

        # Hide crew sidebar when entering agent mode
        self._hide_sidebar()

        if self.agent and not self._is_running:
            self._current_worker = self._run_agent_mode(task)

    async def _parse_crew_command(self, cmd: str) -> None:
        """Parse and execute /crew command"""
        # Remove /crew prefix
        rest = cmd[5:].strip()

        if not rest:
            self._add_system(
                "Usage: /crew <task>\n"
                "Example: /crew https://example.com\n"
                "         /crew 192.168.1.100\n\n"
                "Crew mode spawns specialized workers in parallel:\n"
                "  - recon: Reconnaissance and mapping\n"
                "  - sqli: SQL injection testing\n"
                "  - xss: Cross-site scripting testing\n"
                "  - ssrf: Server-side request forgery\n"
                "  - auth: Authentication testing\n"
                "  - idor: Insecure direct object references\n"
                "  - info: Information disclosure"
            )
            return

        target = rest

        if not self._is_running:
            self._add_user(f"/crew {target}")
            self._show_sidebar()
            self._current_worker = self._run_crew_mode(target)

    def _show_sidebar(self) -> None:
        """Show the sidebar for crew mode."""
        try:
            import time

            sidebar = self.query_one("#sidebar")
            sidebar.add_class("visible")

            chat_area = self.query_one("#chat-area")
            chat_area.add_class("with-sidebar")

            # Setup tree
            tree = self.query_one("#workers-tree", CrewTree)
            tree.root.expand()
            tree.show_root = False

            # Clear old nodes
            tree.root.remove_children()
            self._crew_worker_nodes.clear()
            self._crew_workers.clear()
            self._worker_events.clear()
            self._crew_findings_count = 0

            # Start tracking time and tokens
            self._crew_start_time = time.time()
            self._crew_tokens_used = 0

            # Start stats timer (update every second)
            if self._crew_stats_timer:
                self._crew_stats_timer.stop()
            self._crew_stats_timer = self.set_interval(1.0, self._update_crew_stats)

            # Start spinner timer for running workers (faster interval for smooth animation)
            if self._spinner_timer:
                self._spinner_timer.stop()
            self._spinner_timer = self.set_interval(0.15, self._update_spinner)

            # Add crew root node (no orchestrator - just "CREW" header)
            self._crew_orchestrator_node = tree.root.add(
                "CREW", data={"type": "crew", "id": "crew"}
            )
            self._crew_orchestrator_node.expand()
            tree.select_node(self._crew_orchestrator_node)
            self._viewing_worker_id = None

            # Update stats
            self._update_crew_stats()
        except Exception as e:
            self._add_system(f"[!] Sidebar error: {e}")

    def _hide_sidebar(self) -> None:
        """Hide the sidebar."""
        try:
            # Stop stats timer
            if self._crew_stats_timer:
                self._crew_stats_timer.stop()
                self._crew_stats_timer = None

            sidebar = self.query_one("#sidebar")
            sidebar.remove_class("visible")

            chat_area = self.query_one("#chat-area")
            chat_area.remove_class("with-sidebar")
        except Exception:
            pass

    def _update_crew_stats(self) -> None:
        """Update crew stats panel."""
        try:
            import time

            text = Text()

            # Elapsed time
            text.append("Time:   ", style="bold #d4d4d4")
            if self._crew_start_time:
                elapsed = time.time() - self._crew_start_time
                if elapsed < 60:
                    time_str = f"{int(elapsed)}s"
                elif elapsed < 3600:
                    mins = int(elapsed // 60)
                    secs = int(elapsed % 60)
                    time_str = f"{mins}m {secs}s"
                else:
                    hrs = int(elapsed // 3600)
                    mins = int((elapsed % 3600) // 60)
                    time_str = f"{hrs}h {mins}m"
                text.append(time_str, style="#9a9a9a")
            else:
                text.append("--", style="#525252")

            text.append("\n")

            # Tokens used
            text.append("Tokens: ", style="bold #d4d4d4")
            if self._crew_tokens_used > 0:
                if self._crew_tokens_used >= 1000:
                    token_str = f"{self._crew_tokens_used / 1000:.1f}k"
                else:
                    token_str = str(self._crew_tokens_used)
                text.append(token_str, style="#9a9a9a")
            else:
                text.append("--", style="#525252")

            stats = self.query_one("#crew-stats", Static)
            stats.update(text)
            stats.border_title = "# Stats"
        except Exception:
            pass

    def _update_spinner(self) -> None:
        """Update spinner animation for running workers."""
        try:
            # Advance spinner frame
            self._spinner_frame += 1

            # Only update labels for running workers (efficient)
            has_running = False
            for worker_id, worker in self._crew_workers.items():
                if worker.get("status") == "running":
                    has_running = True
                    # Update the tree node label
                    if worker_id in self._crew_worker_nodes:
                        node = self._crew_worker_nodes[worker_id]
                        node.set_label(self._format_worker_label(worker_id))

            # Stop spinner if no workers are running (save resources)
            if not has_running and self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None
        except Exception:
            pass

    def _add_crew_worker(self, worker_id: str, worker_type: str, task: str) -> None:
        """Add a worker to the sidebar tree."""
        self._crew_workers[worker_id] = {
            "worker_type": worker_type,
            "task": task,
            "status": "pending",
            "findings": 0,
        }

        try:
            label = self._format_worker_label(worker_id)
            node = self._crew_orchestrator_node.add(
                label, data={"type": "worker", "id": worker_id}
            )
            self._crew_worker_nodes[worker_id] = node
            self._crew_orchestrator_node.expand()
            self._update_crew_stats()
        except Exception:
            pass

    def _update_crew_worker(self, worker_id: str, **updates) -> None:
        """Update a worker's state."""
        if worker_id not in self._crew_workers:
            return

        self._crew_workers[worker_id].update(updates)

        # Restart spinner if a worker started running
        if updates.get("status") == "running" and not self._spinner_timer:
            self._spinner_timer = self.set_interval(0.15, self._update_spinner)

        try:
            if worker_id in self._crew_worker_nodes:
                label = self._format_worker_label(worker_id)
                self._crew_worker_nodes[worker_id].set_label(label)
            self._update_crew_stats()
        except Exception:
            pass

    def _format_worker_label(self, worker_id: str) -> Text:
        """Format worker label for tree."""
        worker = self._crew_workers.get(worker_id, {})
        status = worker.get("status", "pending")
        wtype = worker.get("worker_type", "worker")
        findings = worker.get("findings", 0)

        # 4-state icons: working (braille), done (checkmark), warning (!), error (X)
        if status in ("running", "pending"):
            # Animated braille spinner for all in-progress states
            icon = self._spinner_frames[self._spinner_frame % len(self._spinner_frames)]
            color = "#d4d4d4"  # white
        elif status == "complete":
            icon = "✓"
            color = "#22c55e"  # green
        elif status == "warning":
            icon = "!"
            color = "#f59e0b"  # amber/orange
        else:  # error, cancelled, unknown
            icon = "✗"
            color = "#ef4444"  # red

        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(wtype.upper(), style="bold")

        if status == "complete" and findings > 0:
            text.append(f" [{findings}]", style="#22c55e")  # green
        elif status in ("error", "cancelled"):
            # Don't append " !" here since we already have the X icon
            pass

        return text

    def _handle_worker_event(
        self, worker_id: str, event_type: str, data: Dict[str, Any]
    ) -> None:
        """Handle worker events from CrewAgent - updates tree sidebar only."""
        try:
            if event_type == "spawn":
                worker_type = data.get("worker_type", "unknown")
                task = data.get("task", "")
                self._add_crew_worker(worker_id, worker_type, task)
            elif event_type == "status":
                status = data.get("status", "running")
                self._update_crew_worker(worker_id, status=status)
            elif event_type == "tool":
                # Add tool as child node under the agent
                tool_name = data.get("tool", "unknown")
                self._add_tool_to_worker(worker_id, tool_name)
            elif event_type == "tokens":
                # Track token usage
                tokens = data.get("tokens", 0)
                self._crew_tokens_used += tokens
            elif event_type == "complete":
                findings_count = data.get("findings_count", 0)
                self._update_crew_worker(
                    worker_id, status="complete", findings=findings_count
                )
                self._crew_findings_count += findings_count
                self._update_crew_stats()
            elif event_type == "warning":
                # Worker hit max iterations but has results
                self._update_crew_worker(worker_id, status="warning")
                reason = data.get("reason", "Partial completion")
                worker = self._crew_workers.get(worker_id, {})
                wtype = worker.get("worker_type", "worker")
                self._add_system(f"[!] {wtype.upper()} stopped: {reason}")
                self._update_crew_stats()
            elif event_type == "error":
                self._update_crew_worker(worker_id, status="error")
                worker = self._crew_workers.get(worker_id, {})
                wtype = worker.get("worker_type", "worker")
                error_msg = data.get("error", "Unknown error")
                # Only show errors in chat - they're important
                self._add_system(f"[!] {wtype.upper()} failed: {error_msg}")
        except Exception as e:
            self._add_system(f"[!] Worker event error: {e}")

    def _add_tool_to_worker(self, worker_id: str, tool_name: str) -> None:
        """Add a tool usage as child node under worker in tree."""
        try:
            node = self._crew_worker_nodes.get(worker_id)
            if node:
                node.add_leaf(f"  {tool_name}")
                node.expand()
        except Exception:
            pass

    @on(Tree.NodeSelected, "#workers-tree")
    def on_worker_tree_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node = event.node
        if node.data:
            node_type = node.data.get("type")
            if node_type == "crew":
                self._viewing_worker_id = None
            elif node_type == "worker":
                self._viewing_worker_id = node.data.get("id")

    @work(thread=False)
    async def _run_crew_mode(self, target: str) -> None:
        """Run crew mode with sidebar."""
        self._is_running = True
        self._should_stop = False
        self._set_status("thinking", "crew")

        try:
            from ..agents.base_agent import AgentMessage
            from ..agents.crew import CrewOrchestrator
            from ..llm import LLM, ModelConfig

            # Build prior context from assist/agent conversation history
            prior_context = self._build_prior_context()

            llm = LLM(model=self.model, config=ModelConfig(temperature=0.7))

            crew = CrewOrchestrator(
                llm=llm,
                tools=self.all_tools,
                runtime=self.runtime,
                on_worker_event=self._handle_worker_event,
                rag_engine=self.rag_engine,
                target=self.target,
                prior_context=prior_context,
            )
            self._current_crew = crew  # Track for cancellation

            self._add_system(f"@ Task: {target}")

            # Track crew results for memory
            crew_report = None

            async for update in crew.run(target):
                if self._should_stop:
                    await crew.cancel()
                    self._add_system("[!] Stopped by user")
                    break

                phase = update.get("phase", "")

                if phase == "starting":
                    self._set_status("thinking", "crew")

                elif phase == "thinking":
                    # Show the orchestrator's reasoning
                    content = update.get("content", "")
                    if content:
                        self._add_thinking(content)

                elif phase == "tool_call":
                    # Show orchestration tool calls
                    tool = update.get("tool", "")
                    args = update.get("args", {})
                    self._add_tool(tool, str(args))

                elif phase == "tool_result":
                    # Tool results are tracked via worker events
                    pass

                elif phase == "complete":
                    crew_report = update.get("report", "")
                    if crew_report:
                        self._add_assistant(crew_report)

                elif phase == "error":
                    error = update.get("error", "Unknown error")
                    self._add_system(f"[!] Crew error: {error}")

            # Add crew results to main agent's conversation history
            # so assist mode can reference what happened
            if self.agent and crew_report:
                # Add the crew task as a user message
                self.agent.conversation_history.append(
                    AgentMessage(
                        role="user",
                        content=f"[CREW MODE] Run parallel analysis on target: {target}",
                    )
                )
                # Add the crew report as assistant response
                self.agent.conversation_history.append(
                    AgentMessage(role="assistant", content=crew_report)
                )

            self._set_status("complete", "crew")
            self._add_system("+ Crew task complete.")

            # Stop timers
            if self._crew_stats_timer:
                self._crew_stats_timer.stop()
                self._crew_stats_timer = None
            if self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None

            # Clear crew reference
            self._current_crew = None

        except asyncio.CancelledError:
            # Cancel crew workers first
            if self._current_crew:
                await self._current_crew.cancel()
                self._current_crew = None
            self._add_system("[!] Cancelled")
            self._set_status("idle", "crew")
            # Stop timers on cancel
            if self._crew_stats_timer:
                self._crew_stats_timer.stop()
                self._crew_stats_timer = None
            if self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None

        except Exception as e:
            import traceback

            # Cancel crew workers on error too
            if self._current_crew:
                try:
                    await self._current_crew.cancel()
                except Exception:
                    pass
                self._current_crew = None
            self._add_system(f"[!] Crew error: {e}\n{traceback.format_exc()}")
            self._set_status("error")
            # Stop timers on error too
            if self._crew_stats_timer:
                self._crew_stats_timer.stop()
                self._crew_stats_timer = None
            if self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None
        finally:
            self._is_running = False

    @work(thread=False)
    async def _run_assist(self, message: str) -> None:
        """Run in assist mode - single response"""
        if not self.agent:
            self._add_system("[!] Agent not ready")
            return

        self._is_running = True
        self._should_stop = False
        self._set_status("thinking", "assist")

        try:
            async for response in self.agent.assist(message):
                if self._should_stop:
                    self._add_system("[!] Stopped by user")
                    break

                self._set_status("processing")

                # Show thinking/plan FIRST if there's content with tool calls
                if response.content:
                    content = response.content.strip()
                    if response.tool_calls:
                        self._add_thinking(content)
                    else:
                        self._add_assistant(content)

                # Show tool calls (skip 'finish' - internal control)
                if response.tool_calls:
                    for call in response.tool_calls:
                        if call.name == "finish":
                            continue  # Skip - summary shown as final message
                        args_str = str(call.arguments)
                        self._add_tool(call.name, args_str)

                # Show tool results (displayed after execution completes)
                # Skip 'finish' tool - its result is shown as the final summary
                if response.tool_results:
                    for result in response.tool_results:
                        if result.tool_name == "finish":
                            continue  # Skip - summary shown separately
                        if result.success:
                            self._add_tool_result(
                                result.tool_name, result.result or "Done"
                            )
                        else:
                            self._add_tool_result(
                                result.tool_name, f"Error: {result.error}"
                            )

            self._set_status("idle", "assist")

        except asyncio.CancelledError:
            self._add_system("[!] Cancelled")
            self._set_status("idle", "assist")
        except Exception as e:
            self._add_system(f"[!] Error: {e}")
            self._set_status("error")
        finally:
            self._is_running = False

    @work(thread=False)
    async def _run_agent_mode(self, task: str) -> None:
        """Run in agent mode - autonomous until task complete or user stops"""
        if not self.agent:
            self._add_system("[!] Agent not ready")
            return

        self._is_running = True
        self._should_stop = False

        self._set_status("thinking", "agent")

        try:
            async for response in self.agent.agent_loop(task):
                if self._should_stop:
                    self._add_system("[!] Stopped by user")
                    break

                self._set_status("processing")

                # Show thinking/plan FIRST if there's content with tool calls
                if response.content:
                    content = response.content.strip()
                    # If it has tool calls, it's thinking.
                    # If it's marked as intermediate, it's thinking.
                    if response.tool_calls or response.metadata.get("intermediate"):
                        self._add_thinking(content)
                    else:
                        # Check if this is a task completion message
                        if response.metadata.get("task_complete"):
                            self._add_assistant(content)
                        else:
                            self._add_assistant(content)

                # Show tool calls AFTER thinking
                if response.tool_calls:
                    for call in response.tool_calls:
                        # Show all tools including finish
                        args_str = str(call.arguments)
                        self._add_tool(call.name, args_str)

                # Show tool results
                if response.tool_results:
                    for result in response.tool_results:
                        if result.tool_name == "finish":
                            # Skip showing result for finish tool as it's redundant with the tool call display
                            continue

                        if result.success:
                            self._add_tool_result(
                                result.tool_name, result.result or "Done"
                            )
                        else:
                            self._add_tool_result(
                                result.tool_name, f"Error: {result.error}"
                            )

                # Check state
                if self.agent.state.value == "waiting_input":
                    self._set_status("waiting")
                    self._add_system("? Awaiting input...")
                    break
                elif self.agent.state.value == "complete":
                    break

                self._set_status("thinking")

            self._set_status("complete", "agent")
            self._add_system("+ Agent task complete. Back to assist mode.")

            # Return to assist mode
            await asyncio.sleep(1)
            self._set_status("idle", "assist")

        except asyncio.CancelledError:
            self._add_system("[!] Cancelled")
            self._set_status("idle", "assist")
        except Exception as e:
            self._add_system(f"[!] Error: {e}")
            self._set_status("error")
        finally:
            self._is_running = False

    def action_quit_app(self) -> None:
        # Stop any running tasks first
        if self._is_running:
            self._should_stop = True
            if self._current_worker and not self._current_worker.is_finished:
                self._current_worker.cancel()
            if self._current_crew:
                # Schedule cancel but don't wait - we're exiting
                asyncio.create_task(self._cancel_crew())
        self.exit()

    def action_stop_agent(self) -> None:
        if self._is_running:
            self._should_stop = True
            self._add_system("[!] Stopping...")

            # Cancel the running worker to interrupt blocking awaits
            if self._current_worker and not self._current_worker.is_finished:
                self._current_worker.cancel()

            # Cancel crew orchestrator if running
            if self._current_crew:
                asyncio.create_task(self._cancel_crew())

            # Clean up agent state to prevent stale tool responses
            if self.agent:
                self.agent.cleanup_after_cancel()

            # Reconnect MCP servers (they may be in a bad state after cancellation)
            if self.mcp_manager:
                asyncio.create_task(self._reconnect_mcp_after_cancel())

    async def _cancel_crew(self) -> None:
        """Cancel crew orchestrator and all workers."""
        try:
            if self._current_crew:
                await self._current_crew.cancel()
                self._current_crew = None
                # Mark all running workers as cancelled in the UI
                for worker_id, worker in self._crew_workers.items():
                    if worker.get("status") in ("running", "pending"):
                        self._update_crew_worker(worker_id, status="cancelled")
        except Exception:
            pass  # Best effort

    async def _reconnect_mcp_after_cancel(self) -> None:
        """Reconnect MCP servers after cancellation to restore clean state."""
        await asyncio.sleep(0.5)  # Brief delay for cancellation to propagate
        try:
            await self.mcp_manager.reconnect_all()
        except Exception:
            pass  # Best effort - don't crash if reconnect fails

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    async def on_unmount(self) -> None:
        """Cleanup"""
        if self.mcp_manager:
            try:
                await self.mcp_manager.disconnect_all()
                await asyncio.sleep(0.1)
            except Exception:
                pass

        if self.runtime:
            try:
                await self.runtime.stop()
            except Exception:
                pass


# ----- Entry Point -----


def run_tui(
    target: Optional[str] = None,
    model: str = None,
    use_docker: bool = False,
):
    """Run the GhostCrew TUI"""
    app = GhostCrewTUI(
        target=target,
        model=model,
        use_docker=use_docker,
    )
    app.run()


if __name__ == "__main__":
    run_tui()
