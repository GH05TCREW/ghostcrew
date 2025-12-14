<div align="center">

<img src="assets/ghostcrew-logo.png" alt="GhostCrew Logo" width="220" style="margin-bottom: 20px;"/>

# GHOSTCREW
### AI Penetration Testing Agents

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/) [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE.txt) [![Version](https://img.shields.io/badge/Version-0.2.0-orange.svg)](https://github.com/GH05TCREW/ghostcrew/releases) [![Security](https://img.shields.io/badge/Security-Penetration%20Testing-red.svg)](https://github.com/GH05TCREW/ghostcrew) [![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://github.com/GH05TCREW/ghostcrew)

[🇺🇸 English](README.md) | [🇨🇳 中文文档](README_zh.md)

</div>

https://github.com/user-attachments/assets/a67db2b5-672a-43df-b709-149c8eaee975

## Requirements

- Python 3.10+
- API key for OpenAI, Anthropic, or other LiteLLM-supported provider

## Install

```bash
# Clone
git clone https://github.com/GH05TCREW/ghostcrew.git
cd ghostcrew

# Setup (creates venv, installs deps)
.\scripts\setup.ps1   # Windows
./scripts/setup.sh    # Linux/macOS

# Or manual
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/macOS
pip install -e ".[all]"
playwright install chromium  # Required for browser tool
```

## Configure

Create `.env` in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
GHOSTCREW_MODEL=claude-sonnet-4-20250514
```

Or for OpenAI:

```
OPENAI_API_KEY=sk-...
GHOSTCREW_MODEL=gpt-5
```

Any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers) works.

## Run

```bash
ghostcrew                    # Launch TUI
ghostcrew -t 192.168.1.1     # Launch with target
ghostcrew --docker           # Run tools in Docker container
```

## Docker

Run tools inside a Docker container for isolation and pre-installed pentesting tools.

### Option 1: Pull pre-built image (fastest)

```bash
# Base image with nmap, netcat, curl
docker run -it --rm \
  -e ANTHROPIC_API_KEY=your-key \
  -e GHOSTCREW_MODEL=claude-sonnet-4-20250514 \
  ghcr.io/gh05tcrew/ghostcrew:latest

# Kali image with metasploit, sqlmap, hydra, etc.
docker run -it --rm \
  -e ANTHROPIC_API_KEY=your-key \
  ghcr.io/gh05tcrew/ghostcrew:kali
```

### Option 2: Build locally

```bash
# Build
docker compose build

# Run
docker compose run --rm ghostcrew

# Or with Kali
docker compose --profile kali build
docker compose --profile kali run --rm ghostcrew-kali
```

The container runs GhostCrew with access to Linux pentesting tools. The agent can use `nmap`, `msfconsole`, `sqlmap`, etc. directly via the terminal tool.

Requires Docker to be installed and running.

## Modes

GhostCrew has three modes, accessible via commands in the TUI:

| Mode | Command | Description |
|------|---------|-------------|
| Assist | (default) | Chat with the agent. You control the flow. |
| Agent | `/agent <task>` | Autonomous execution of a single task. |
| Crew | `/crew <task>` | Multi-agent mode. Orchestrator spawns specialized workers. |

### TUI Commands

```
/agent <task>    Run autonomous agent on task
/crew <task>     Run multi-agent crew on task
/target <host>   Set target
/tools           List available tools
/notes           Show saved notes
/report          Generate report from session
/memory          Show token/memory usage
/prompt          Show system prompt
/clear           Clear chat and history
/quit            Exit (also /exit, /q)
/help            Show help (also /h, /?)
```

Press `Esc` to stop a running agent. `Ctrl+Q` to quit.

## Tools

GhostCrew includes built-in tools and supports MCP (Model Context Protocol) for extensibility.

**Built-in tools:** `terminal`, `browser`, `notes`, `web_search` (requires `TAVILY_API_KEY`)

### MCP Integration

Add external tools via MCP servers in `ghostcrew/mcp/mcp_servers.json`:

```json
{
  "mcpServers": {
    "nmap": {
      "command": "npx",
      "args": ["-y", "gc-nmap-mcp"],
      "env": {
        "NMAP_PATH": "/usr/bin/nmap"
      }
    }
  }
}
```

### CLI Tool Management

```bash
ghostcrew tools list         # List all tools
ghostcrew tools info <name>  # Show tool details
ghostcrew mcp list           # List MCP servers
ghostcrew mcp add <name> <command> [args...]  # Add MCP server
ghostcrew mcp test <name>    # Test MCP connection
```

## Knowledge

- **RAG:** Place methodologies, CVEs, or wordlists in `ghostcrew/knowledge/sources/` for automatic context injection.
- **Notes:** Agents save findings to `loot/notes.json` with categories (`credential`, `vulnerability`, `finding`, `artifact`). Notes persist across sessions and are injected into agent context.
- **Shadow Graph:** In Crew mode, the orchestrator builds a knowledge graph from notes to derive strategic insights (e.g., "We have credentials for host X").

## Project Structure

```
ghostcrew/
  agents/         # Agent implementations
  config/         # Settings and constants
  interface/      # TUI and CLI
  knowledge/      # RAG system and shadow graph
  llm/            # LiteLLM wrapper
  mcp/            # MCP client and server configs
  runtime/        # Execution environment
  tools/          # Built-in tools
```

## Development

```bash
pip install -e ".[dev]"
pytest                    # Run tests
pytest --cov=ghostcrew    # With coverage
black ghostcrew           # Format
ruff check ghostcrew      # Lint
```

## Legal

Only use against systems you have explicit authorization to test. Unauthorized access is illegal.

## License

MIT
