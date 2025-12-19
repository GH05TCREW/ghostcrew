"""Interface utilities for PentestAgent."""

from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ASCII Art Banner
ASCII_BANNER = r"""
             ('-. .-.               .-')    .-') _            _  .-')     ('-.    (`\ .-') /`
            ( OO )  /              ( OO ). (  OO) )          ( \( -O )  _(  OO)    `.( OO ),'
  ,----.    ,--. ,--. .-'),-----. (_)---\_)/     '._  .-----. ,------. (,------.,--./  .--.
 '  .-./-') |  | |  |( OO'  .-.  '/    _ | |'--...__)'  .--./ |   /`. ' |  .---'|      |  |
 |  |_( O- )|   .|  |/   |  | |  |\  :` `. '--.  .--'|  |('-. |  /  | | |  |    |  |   |  |,
 |  | .--, \|       |\_) |  |\|  | '..`''.)   |  |  /_) |OO  )|  |_.' |(|  '--. |  |.'.|  |_)
(|  | '. (_/|  .-.  |  \ |  | |  |.-._)   \   |  |  ||  |`-'| |  .  '.' |  .--' |         |
 |  '--'  | |  | |  |   `'  '-'  '\       /   |  | (_'  '--'\ |  |\  \  |  `---.|   ,'.   |
  `------'  `--' `--'     `-----'  `-----'    `--'    `-----' `--' '--' `------''--'   '--'
"""


def print_banner():
    """Print the PentestAgent banner."""
    console.print(f"[bold white]{ASCII_BANNER}[/]")
    console.print(
        "[bold white]====================== PENTESTAGENT =======================[/]"
    )
    console.print(
        "[dim white]        AI Penetration Testing Agents  v0.2.0[/dim white]\n"
    )


def format_finding(
    title: str,
    severity: str,
    target: str,
    description: str,
    evidence: str = "",
    impact: str = "",
    remediation: str = "",
) -> Panel:
    """
    Format a security finding for display.

    Args:
        title: Finding title
        severity: Severity level
        target: Affected target
        description: Description of the finding
        evidence: Proof/evidence
        impact: Potential impact
        remediation: How to fix

    Returns:
        Rich Panel with formatted finding
    """
    severity_colors = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "blue",
        "informational": "dim",
    }

    color = severity_colors.get(severity.lower(), "white")

    content = f"""
[bold]Target:[/] {target}
[{color}]Severity:[/{color}] [{color}]{severity.upper()}[/{color}]

[bold]Description:[/]
{description}
"""

    if evidence:
        content += f"\n[bold]Evidence:[/]\n{evidence}\n"

    if impact:
        content += f"\n[bold]Impact:[/]\n{impact}\n"

    if remediation:
        content += f"\n[bold]Remediation:[/]\n{remediation}\n"

    return Panel(content, title=f"[bold]{title}[/]", border_style=color)


def format_tool_call(tool_call: Any) -> str:
    """
    Format a tool call for display.

    Args:
        tool_call: The tool call object

    Returns:
        Formatted string
    """
    name = tool_call.name if hasattr(tool_call, "name") else str(tool_call)
    args = tool_call.arguments if hasattr(tool_call, "arguments") else {}

    # Truncate long arguments
    args_str = str(args)
    if len(args_str) > 100:
        args_str = args_str[:100] + "..."

    return f"[bold yellow]⚡ Tool:[/] {name}\n[dim]{args_str}[/dim]"


def print_status(
    target: Optional[str] = None,
    scope: Optional[list] = None,
    agent_state: str = "idle",
    tools_count: int = 0,
    findings_count: int = 0,
):
    """
    Print current status information.

    Args:
        target: Current target
        scope: Current scope
        agent_state: Agent state
        tools_count: Number of loaded tools
        findings_count: Number of findings
    """
    table = Table(title="PentestAgent Status", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Target", target or "Not set")
    table.add_row("Scope", ", ".join(scope) if scope else "Not set")
    table.add_row("Agent State", agent_state)
    table.add_row("Tools Loaded", str(tools_count))
    table.add_row("Findings", str(findings_count))

    console.print(table)


def format_scan_progress(current: int, total: int, current_item: str) -> str:
    """
    Format scan progress for display.

    Args:
        current: Current item number
        total: Total items
        current_item: Current item being scanned

    Returns:
        Formatted progress string
    """
    percentage = (current / total * 100) if total > 0 else 0
    bar_width = 30
    filled = int(bar_width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_width - filled)

    return f"[{bar}] {percentage:.1f}% ({current}/{total}) - {current_item}"


def truncate_output(output: str, max_lines: int = 50) -> str:
    """
    Truncate long output for display.

    Args:
        output: Output to truncate
        max_lines: Maximum number of lines

    Returns:
        Truncated output
    """
    lines = output.split("\n")

    if len(lines) <= max_lines:
        return output

    half = max_lines // 2
    truncated = (
        lines[:half]
        + [f"\n... ({len(lines) - max_lines} lines omitted) ...\n"]
        + lines[-half:]
    )

    return "\n".join(truncated)


def colorize_severity(severity: str) -> str:
    """
    Add color to severity text.

    Args:
        severity: Severity level

    Returns:
        Colorized severity string
    """
    colors = {
        "critical": "[red bold]CRITICAL[/]",
        "high": "[red]HIGH[/]",
        "medium": "[yellow]MEDIUM[/]",
        "low": "[blue]LOW[/]",
        "informational": "[dim]INFO[/]",
        "info": "[dim]INFO[/]",
    }

    return colors.get(severity.lower(), severity)


def format_command_output(
    command: str, exit_code: int, stdout: str, stderr: str
) -> Panel:
    """
    Format command output for display.

    Args:
        command: The command that was run
        exit_code: Exit code
        stdout: Standard output
        stderr: Standard error

    Returns:
        Rich Panel with formatted output
    """
    success = exit_code == 0
    border_color = "green" if success else "red"

    content = f"[bold]Command:[/] {command}\n"
    content += f"[bold]Exit Code:[/] {exit_code}\n"

    if stdout:
        content += f"\n[bold]Output:[/]\n{truncate_output(stdout)}"

    if stderr:
        content += f"\n[bold red]Errors:[/]\n{truncate_output(stderr)}"

    return Panel(content, title="Command Result", border_style=border_color)
