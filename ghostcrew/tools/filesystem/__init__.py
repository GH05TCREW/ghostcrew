"""Filesystem tool for GhostCrew - precise file reading and editing."""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from ..registry import ToolSchema, register_tool

if TYPE_CHECKING:
    from ...runtime import Runtime


# Safety: Restrict operations to workspace
_WORKSPACE_ROOT: Optional[Path] = None


def set_workspace_root(path: Path) -> None:
    """Set the workspace root for safety checks."""
    global _WORKSPACE_ROOT
    _WORKSPACE_ROOT = path.resolve()


def _validate_path(filepath: str) -> Path:
    """Validate and resolve a file path within the workspace."""
    path = Path(filepath).resolve()
    
    # If workspace root is set, ensure path is within it
    if _WORKSPACE_ROOT:
        try:
            path.relative_to(_WORKSPACE_ROOT)
        except ValueError:
            raise ValueError(f"Path '{filepath}' is outside workspace root")
    
    return path


@register_tool(
    name="read_file",
    description="Read contents of a file. Can read entire file or specific line range. Use this to examine source code, configs, or any text file.",
    schema=ToolSchema(
        properties={
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            },
            "start_line": {
                "type": "integer",
                "description": "Starting line number (1-indexed). If omitted, reads from beginning.",
            },
            "end_line": {
                "type": "integer",
                "description": "Ending line number (1-indexed, inclusive). If omitted, reads to end.",
            },
        },
        required=["path"],
    ),
    category="filesystem",
)
async def read_file(arguments: dict, runtime: "Runtime") -> str:
    """
    Read a file's contents, optionally within a line range.
    
    Args:
        arguments: Dictionary with 'path' and optional 'start_line', 'end_line'
        runtime: The runtime environment
        
    Returns:
        File contents with line numbers
    """
    filepath = arguments["path"]
    start_line = arguments.get("start_line")
    end_line = arguments.get("end_line")
    
    try:
        path = _validate_path(filepath)
        
        if not path.exists():
            return f"Error: File not found: {filepath}"
        
        if not path.is_file():
            return f"Error: Not a file: {filepath}"
        
        # Read file content
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")
        
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Handle line range
        start_idx = (start_line - 1) if start_line else 0
        end_idx = end_line if end_line else total_lines
        
        # Clamp to valid range
        start_idx = max(0, min(start_idx, total_lines))
        end_idx = max(0, min(end_idx, total_lines))
        
        if start_idx >= end_idx:
            return f"Error: Invalid line range {start_line}-{end_line} (file has {total_lines} lines)"
        
        # Format output with line numbers
        selected_lines = lines[start_idx:end_idx]
        output_lines = []
        for i, line in enumerate(selected_lines, start=start_idx + 1):
            output_lines.append(f"{i:4d} | {line}")
        
        header = f"File: {filepath} (lines {start_idx + 1}-{end_idx} of {total_lines})"
        return f"{header}\n{'─' * 60}\n" + "\n".join(output_lines)
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


@register_tool(
    name="write_file",
    description="Write content to a file. Creates the file if it doesn't exist, or overwrites if it does. Use for creating PoCs, scripts, or config files.",
    schema=ToolSchema(
        properties={
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
            "append": {
                "type": "boolean",
                "description": "If true, append to file instead of overwriting. Default: false",
            },
        },
        required=["path", "content"],
    ),
    category="filesystem",
)
async def write_file(arguments: dict, runtime: "Runtime") -> str:
    """
    Write content to a file.
    
    Args:
        arguments: Dictionary with 'path', 'content', and optional 'append'
        runtime: The runtime environment
        
    Returns:
        Success or error message
    """
    filepath = arguments["path"]
    content = arguments["content"]
    append = arguments.get("append", False)
    
    try:
        path = _validate_path(filepath)
        
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        
        action = "Appended to" if append else "Wrote"
        return f"{action} {len(content)} bytes to {filepath}"
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


@register_tool(
    name="replace_in_file",
    description="Replace text in a file. Finds exact match of 'old_string' and replaces with 'new_string'. Include surrounding context in old_string to ensure unique match.",
    schema=ToolSchema(
        properties={
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find and replace (include context lines for unique match)",
            },
            "new_string": {
                "type": "string",
                "description": "Text to replace old_string with",
            },
        },
        required=["path", "old_string", "new_string"],
    ),
    category="filesystem",
)
async def replace_in_file(arguments: dict, runtime: "Runtime") -> str:
    """
    Replace text in a file.
    
    Args:
        arguments: Dictionary with 'path', 'old_string', 'new_string'
        runtime: The runtime environment
        
    Returns:
        Success or error message with diff preview
    """
    filepath = arguments["path"]
    old_string = arguments["old_string"]
    new_string = arguments["new_string"]
    
    try:
        path = _validate_path(filepath)
        
        if not path.exists():
            return f"Error: File not found: {filepath}"
        
        # Read current content
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")
        
        # Count occurrences
        count = content.count(old_string)
        
        if count == 0:
            return f"Error: String not found in {filepath}. Make sure old_string matches exactly (including whitespace)."
        
        if count > 1:
            return f"Error: Found {count} matches in {filepath}. Include more context in old_string to make it unique."
        
        # Perform replacement
        new_content = content.replace(old_string, new_string, 1)
        path.write_text(new_content, encoding="utf-8")
        
        # Show what changed
        old_preview = old_string[:100] + "..." if len(old_string) > 100 else old_string
        new_preview = new_string[:100] + "..." if len(new_string) > 100 else new_string
        
        return f"Replaced in {filepath}:\n- {repr(old_preview)}\n+ {repr(new_preview)}"
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error replacing in file: {e}"


@register_tool(
    name="list_directory",
    description="List contents of a directory. Shows files and subdirectories with basic info.",
    schema=ToolSchema(
        properties={
            "path": {
                "type": "string",
                "description": "Path to the directory to list. Default: current directory",
            },
            "recursive": {
                "type": "boolean",
                "description": "If true, list recursively (max 3 levels). Default: false",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern to filter results (e.g., '*.py', '*.js')",
            },
        },
        required=[],
    ),
    category="filesystem",
)
async def list_directory(arguments: dict, runtime: "Runtime") -> str:
    """
    List directory contents.
    
    Args:
        arguments: Dictionary with optional 'path', 'recursive', 'pattern'
        runtime: The runtime environment
        
    Returns:
        Directory listing
    """
    dirpath = arguments.get("path", ".")
    recursive = arguments.get("recursive", False)
    pattern = arguments.get("pattern")
    
    try:
        path = _validate_path(dirpath)
        
        if not path.exists():
            return f"Error: Directory not found: {dirpath}"
        
        if not path.is_dir():
            return f"Error: Not a directory: {dirpath}"
        
        entries = []
        
        if recursive:
            # Recursive listing with depth limit
            for root, dirs, files in os.walk(path):
                root_path = Path(root)
                depth = len(root_path.relative_to(path).parts)
                if depth > 3:
                    dirs.clear()  # Don't go deeper
                    continue
                
                rel_root = root_path.relative_to(path)
                prefix = "  " * depth
                
                for d in sorted(dirs):
                    if not d.startswith('.'):
                        entries.append(f"{prefix}{d}/")
                
                for f in sorted(files):
                    if pattern and not Path(f).match(pattern):
                        continue
                    if not f.startswith('.'):
                        file_path = root_path / f
                        size = file_path.stat().st_size
                        entries.append(f"{prefix}{f} ({_format_size(size)})")
        else:
            # Single-level listing
            for item in sorted(path.iterdir()):
                if item.name.startswith('.'):
                    continue
                if pattern and not item.match(pattern):
                    continue
                
                if item.is_dir():
                    entries.append(f"{item.name}/")
                else:
                    size = item.stat().st_size
                    entries.append(f"{item.name} ({_format_size(size)})")
        
        if not entries:
            return f"Directory {dirpath} is empty" + (f" (pattern: {pattern})" if pattern else "")
        
        header = f"Directory: {dirpath}" + (f" (pattern: {pattern})" if pattern else "")
        return f"{header}\n{'─' * 40}\n" + "\n".join(entries)
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


def _format_size(size: int) -> str:
    """Format file size in human-readable form."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != 'B' else f"{size}B"
        size /= 1024
    return f"{size:.1f}TB"
