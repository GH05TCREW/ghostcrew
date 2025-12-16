"""Non-interactive CLI mode for GhostCrew."""

import asyncio
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

console = Console()

# Ghost theme colors (matching TUI)
GHOST_PRIMARY = "#d4d4d4"  # light gray - primary text
GHOST_SECONDARY = "#9a9a9a"  # medium gray - secondary text
GHOST_DIM = "#6b6b6b"  # dim gray - muted text
GHOST_BORDER = "#3a3a3a"  # dark gray - borders
GHOST_ACCENT = "#7a7a7a"  # accent gray


async def run_cli(
    target: str,
    model: str,
    task: str = None,
    report: str = None,
    max_loops: int = 50,
    use_docker: bool = False,
):
    """
    Run GhostCrew in non-interactive mode.

    Args:
        target: Target to test
        model: LLM model to use
        task: Optional task description
        report: Report path ("auto" for loot/reports/<target>_<timestamp>.md)
        max_loops: Max agent loops before stopping
        use_docker: Run tools in Docker container
    """
    from ..agents.ghostcrew_agent import GhostCrewAgent
    from ..knowledge import RAGEngine
    from ..llm import LLM
    from ..runtime.docker_runtime import DockerRuntime
    from ..runtime.runtime import LocalRuntime
    from ..tools import get_all_tools

    # Startup panel
    start_text = Text()
    start_text.append("GHOSTCREW", style=f"bold {GHOST_PRIMARY}")
    start_text.append(" - Non-interactive Mode\n\n", style=GHOST_DIM)
    start_text.append("Target: ", style=GHOST_SECONDARY)
    start_text.append(f"{target}\n", style=GHOST_PRIMARY)
    start_text.append("Model: ", style=GHOST_SECONDARY)
    start_text.append(f"{model}\n", style=GHOST_PRIMARY)
    start_text.append("Runtime: ", style=GHOST_SECONDARY)
    start_text.append(f"{'Docker' if use_docker else 'Local'}\n", style=GHOST_PRIMARY)
    start_text.append("Max loops: ", style=GHOST_SECONDARY)
    start_text.append(f"{max_loops}\n", style=GHOST_PRIMARY)

    task_msg = task or f"Perform a penetration test on {target}"
    start_text.append("Task: ", style=GHOST_SECONDARY)
    start_text.append(task_msg, style=GHOST_PRIMARY)

    console.print()
    console.print(
        Panel(
            start_text, title=f"[{GHOST_SECONDARY}]Starting", border_style=GHOST_BORDER
        )
    )
    console.print()

    # Initialize RAG if knowledge exists
    rag = None
    knowledge_path = Path("knowledge")
    if knowledge_path.exists():
        try:
            rag = RAGEngine(knowledge_path=knowledge_path)
            rag.index()
        except Exception:
            pass

    # Initialize MCP if config exists (silently skip failures)
    mcp_manager = None
    mcp_count = 0
    try:
        from ..mcp import MCPManager
        from ..tools import register_tool_instance

        mcp_manager = MCPManager()
        if mcp_manager.config_path.exists():
            mcp_tools = await mcp_manager.connect_all()
            for tool in mcp_tools:
                register_tool_instance(tool)
            mcp_count = len(mcp_tools)
            if mcp_count > 0:
                console.print(f"[{GHOST_DIM}]Loaded {mcp_count} MCP tools[/]")
    except Exception:
        pass  # MCP is optional, continue without it

    # Initialize runtime - Docker or Local
    if use_docker:
        console.print(f"[{GHOST_DIM}]Starting Docker container...[/]")
        runtime = DockerRuntime(mcp_manager=mcp_manager)
    else:
        runtime = LocalRuntime(mcp_manager=mcp_manager)
    await runtime.start()

    llm = LLM(model=model, rag_engine=rag)
    tools = get_all_tools()

    agent = GhostCrewAgent(
        llm=llm,
        tools=tools,
        runtime=runtime,
        target=target,
        rag_engine=rag,
    )

    # Stats tracking
    start_time = time.time()
    tool_count = 0
    iteration = 0
    findings_count = 0  # Count of notes/findings recorded
    findings = []  # Store actual findings text
    total_tokens = 0  # Track total token usage
    messages = []  # Store agent messages
    tool_log = []  # Log of tools executed (ts, name, command, result, exit_code)
    last_content = ""
    last_msg_intermediate = False  # Track if previous message was intermediate (to avoid double counting tokens)
    stopped_reason = None

    def print_status(msg: str, style: str = GHOST_DIM):
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        timestamp = f"[{mins:02d}:{secs:02d}]"
        console.print(f"[{GHOST_DIM}]{timestamp}[/] [{style}]{msg}[/]")

    def generate_report() -> str:
        """Generate markdown report."""
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)

        status_text = "Complete"
        if stopped_reason:
            status_text = f"Interrupted ({stopped_reason})"

        lines = [
            "# GhostCrew Penetration Test Report",
            "",
            "## Executive Summary",
            "",
        ]

        # Add AI summary at top if available
        if findings:
            lines.append(findings[-1])
            lines.append("")
        else:
            lines.append("*Assessment incomplete - no analysis generated.*")
            lines.append("")

        # Engagement details table
        lines.extend(
            [
                "## Engagement Details",
                "",
                "| Field | Value |",
                "|-------|-------|",
                f"| **Target** | `{target}` |",
                f"| **Task** | {task_msg} |",
                f"| **Date** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
                f"| **Duration** | {mins}m {secs}s |",
                f"| **Commands Executed** | {tool_count} |",
                f"| **Status** | {status_text} |",
                "",
                "---",
                "",
                "## Commands Executed",
                "",
            ]
        )

        # Detailed command log
        for i, entry in enumerate(tool_log, 1):
            ts = entry.get("ts", "??:??")
            name = entry.get("name", "unknown")
            command = entry.get("command", "")
            result = entry.get("result", "")
            exit_code = entry.get("exit_code")

            lines.append(f"### {i}. {name} `[{ts}]`")
            lines.append("")

            if command:
                lines.append("**Command:**")
                lines.append("```")
                lines.append(command)
                lines.append("```")
                lines.append("")

            if exit_code is not None:
                lines.append(f"**Exit Code:** `{exit_code}`")
                lines.append("")

            if result:
                lines.append("**Output:**")
                lines.append("```")
                # Limit output to 2000 chars per command for report size
                if len(result) > 2000:
                    lines.append(result[:2000])
                    lines.append(f"\n... (truncated, {len(result)} total chars)")
                else:
                    lines.append(result)
                lines.append("```")
                lines.append("")

        # Findings section
        lines.extend(
            [
                "---",
                "",
                "## Analysis",
                "",
            ]
        )

        if findings:
            for i, finding in enumerate(findings, 1):
                if len(findings) > 1:
                    lines.append(f"### Analysis {i}")
                    lines.append("")
                lines.append(finding)
                lines.append("")
        else:
            lines.append(
                "*No AI analysis generated. Try running with higher `--max` value.*"
            )
            lines.append("")

        # Footer
        lines.extend(
            [
                "---",
                "",
                f"*Report generated by GhostCrew on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ]
        )

        return "\n".join(lines)

    def save_report():
        """Save report to file."""
        if not report:
            return

        # Determine path
        if report == "auto":
            reports_dir = Path("loot/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            safe_target = target.replace("://", "_").replace("/", "_").replace(":", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = reports_dir / f"{safe_target}_{timestamp}.md"
        else:
            report_path = Path(report)
            report_path.parent.mkdir(parents=True, exist_ok=True)

        content = generate_report()
        report_path.write_text(content, encoding="utf-8")
        console.print(f"[{GHOST_SECONDARY}]Report saved: {report_path}[/]")

    async def generate_summary():
        """Ask the LLM to summarize findings when stopped early."""
        if not tool_log:
            return None

        print_status("Generating summary...", GHOST_SECONDARY)

        # Build context from tool results (use full results, not truncated)
        context_lines = ["Summarize the penetration test findings so far:\n"]
        context_lines.append(f"Target: {target}")
        context_lines.append(f"Tools executed: {tool_count}\n")

        for entry in tool_log[-10:]:  # Last 10 tools
            name = entry.get("name", "unknown")
            command = entry.get("command", "")
            result = entry.get("result", "")[:500]  # Limit for context window
            context_lines.append(f"- **{name}**: `{command}`")
            if result:
                context_lines.append(f"  Output: {result}")

        context_lines.append(
            "\nProvide a brief summary of what was discovered and any security concerns found."
        )

        try:
            response = await llm.generate(
                system_prompt="You are a penetration testing assistant. Summarize the findings concisely.",
                messages=[{"role": "user", "content": "\n".join(context_lines)}],
                tools=[],
            )
            return response.content
        except Exception:
            return None

    async def print_summary(interrupted: bool = False):
        nonlocal messages

        # Generate summary if we don't have messages yet
        if not messages and tool_log:
            summary = await generate_summary()
            if summary:
                messages.append(summary)

        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)

        title = "Interrupted" if interrupted else "Finished"
        status = "PARTIAL RESULTS" if interrupted else "COMPLETE"
        if stopped_reason:
            status = f"STOPPED ({stopped_reason})"

        final_text = Text()
        final_text.append(f"{status}\n\n", style=f"bold {GHOST_PRIMARY}")
        final_text.append("Duration: ", style=GHOST_DIM)
        final_text.append(f"{mins}m {secs}s\n", style=GHOST_SECONDARY)
        final_text.append("Loops: ", style=GHOST_DIM)
        final_text.append(f"{iteration}/{max_loops}\n", style=GHOST_SECONDARY)
        final_text.append("Tools: ", style=GHOST_DIM)
        final_text.append(f"{tool_count}\n", style=GHOST_SECONDARY)

        if total_tokens > 0:
            final_text.append("Tokens: ", style=GHOST_DIM)
            final_text.append(f"{total_tokens:,}\n", style=GHOST_SECONDARY)

        if findings_count > 0:
            final_text.append("Findings: ", style=GHOST_DIM)
            final_text.append(f"{findings_count}", style=GHOST_SECONDARY)

        console.print()
        console.print(
            Panel(
                final_text,
                title=f"[{GHOST_SECONDARY}]{title}",
                border_style=GHOST_BORDER,
            )
        )

        # Show summary/messages only if it's new content (not just displayed)
        if messages and messages[-1] != last_content:
            console.print()
            console.print(
                Panel(
                    Markdown(messages[-1]),
                    title=f"[{GHOST_PRIMARY}]Summary",
                    border_style=GHOST_BORDER,
                )
            )

        # Save report
        save_report()

    print_status("Initializing agent...")

    try:
        async for response in agent.agent_loop(task_msg):
            iteration += 1

            # Track token usage
            if response.usage:
                usage = response.usage.get("total_tokens", 0)
                is_intermediate = response.metadata.get("intermediate", False)
                has_tools = bool(response.tool_calls)

                # Logic to avoid double counting:
                # 1. Intermediate messages (thinking) always count
                # 2. Tool messages count ONLY if not preceded by intermediate message
                if is_intermediate:
                    total_tokens += usage
                    last_msg_intermediate = True
                elif has_tools:
                    if not last_msg_intermediate:
                        total_tokens += usage
                    last_msg_intermediate = False
                else:
                    # Other messages (like plan)
                    total_tokens += usage
                    last_msg_intermediate = False

            # Show tool calls and results as they happen
            if response.tool_calls:
                for i, call in enumerate(response.tool_calls):
                    tool_count += 1
                    name = getattr(call, "name", None) or getattr(
                        call.function, "name", "tool"
                    )

                    # Track findings (notes tool)
                    if name == "notes":
                        findings_count += 1
                        try:
                            args = getattr(call, "arguments", None) or getattr(
                                call.function, "arguments", "{}"
                            )
                            if isinstance(args, str):
                                import json

                                args = json.loads(args)
                            if isinstance(args, dict):
                                note_content = args.get("content", "") or args.get(
                                    "note", ""
                                )
                                if note_content:
                                    findings.append(note_content)
                        except Exception:
                            pass

                    elapsed = int(time.time() - start_time)
                    mins, secs = divmod(elapsed, 60)
                    ts = f"{mins:02d}:{secs:02d}"

                    # Get result if available
                    if response.tool_results and i < len(response.tool_results):
                        tr = response.tool_results[i]
                        result_text = tr.result or tr.error or ""
                        if result_text:
                            # Truncate for display
                            preview = result_text[:200].replace("\n", " ")
                            if len(result_text) > 200:
                                preview += "..."

                    # Parse args for command extraction
                    command_text = ""
                    exit_code = None
                    try:
                        args = getattr(call, "arguments", None) or getattr(
                            call.function, "arguments", "{}"
                        )
                        if isinstance(args, str):
                            import json

                            args = json.loads(args)
                        if isinstance(args, dict):
                            command_text = args.get("command", "")
                    except Exception:
                        pass

                    # Extract exit code from result
                    if response.tool_results and i < len(response.tool_results):
                        tr = response.tool_results[i]
                        full_result = tr.result or tr.error or ""
                        # Try to parse exit code
                        if "Exit Code:" in full_result:
                            try:
                                import re

                                match = re.search(r"Exit Code:\s*(\d+)", full_result)
                                if match:
                                    exit_code = int(match.group(1))
                            except Exception:
                                pass
                    else:
                        full_result = ""

                    # Store full data for report (not truncated)
                    tool_log.append(
                        {
                            "ts": ts,
                            "name": name,
                            "command": command_text,
                            "result": full_result,
                            "exit_code": exit_code,
                        }
                    )

                    # Metasploit-style output with better spacing
                    console.print()  # Blank line before each tool
                    print_status(f"$ {name} ({tool_count})", GHOST_ACCENT)

                    # Show command/args on separate indented line (truncated for display)
                    if command_text:
                        display_cmd = command_text[:80]
                        if len(command_text) > 80:
                            display_cmd += "..."
                        console.print(f"         [{GHOST_DIM}]{display_cmd}[/]")

                    # Show result on separate line with status indicator
                    if response.tool_results and i < len(response.tool_results):
                        tr = response.tool_results[i]
                        if tr.error:
                            console.print(
                                f"         [{GHOST_DIM}][!] {tr.error[:100]}[/]"
                            )
                        elif tr.result:
                            # Show exit code or brief result
                            result_line = tr.result[:100].replace("\n", " ")
                            if exit_code == 0 or "success" in result_line.lower():
                                console.print(f"         [{GHOST_DIM}][+] OK[/]")
                            elif exit_code is not None and exit_code != 0:
                                console.print(
                                    f"         [{GHOST_DIM}][-] Exit {exit_code}[/]"
                                )
                            else:
                                console.print(
                                    f"         [{GHOST_DIM}][*] {result_line[:60]}...[/]"
                                )

            # Print assistant content immediately (analysis/findings)
            if response.content and response.content != last_content:
                last_content = response.content
                messages.append(response.content)

                console.print()
                console.print(
                    Panel(
                        Markdown(response.content),
                        title=f"[{GHOST_PRIMARY}]GhostCrew",
                        border_style=GHOST_BORDER,
                    )
                )
                console.print()

            # Check max loops limit
            if iteration >= max_loops:
                stopped_reason = "max loops reached"
                console.print()
                print_status(f"Max loops limit reached ({max_loops})", "yellow")
                raise StopIteration()

        await print_summary(interrupted=False)

    except StopIteration:
        await print_summary(interrupted=True)
    except (KeyboardInterrupt, asyncio.CancelledError):
        stopped_reason = "user interrupt"
        await print_summary(interrupted=True)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/]")
        stopped_reason = f"error: {e}"
        await print_summary(interrupted=True)

    finally:
        # Cleanup MCP connections first
        if mcp_manager:
            try:
                await mcp_manager.disconnect_all()
                await asyncio.sleep(0.1)  # Allow transports to close cleanly
            except Exception:
                pass

        # Then stop runtime
        if runtime:
            try:
                await runtime.stop()
            except Exception:
                pass
