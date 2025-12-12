"""Code search tool for GhostCrew - semantic code navigation and analysis."""

import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ..registry import ToolSchema, register_tool

if TYPE_CHECKING:
    from ...runtime import Runtime


# Maximum results to prevent context overflow
MAX_RESULTS = 20
MAX_CONTEXT_LINES = 3


@register_tool(
    name="search_code",
    description="Search for code patterns across files. Supports regex and literal search. Returns matches with surrounding context. Use for finding function definitions, variable usages, API endpoints, or security-relevant patterns.",
    schema=ToolSchema(
        properties={
            "query": {
                "type": "string",
                "description": "Search pattern (text or regex)",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in. Default: current directory",
            },
            "pattern": {
                "type": "string",
                "description": "File glob pattern to filter (e.g., '*.py', '*.js'). Default: all files",
            },
            "regex": {
                "type": "boolean",
                "description": "Treat query as regex pattern. Default: false (literal search)",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search. Default: false",
            },
            "context_lines": {
                "type": "integer",
                "description": "Number of context lines before/after match. Default: 3",
            },
        },
        required=["query"],
    ),
    category="code",
)
async def search_code(arguments: dict, runtime: "Runtime") -> str:
    """
    Search for code patterns across files.
    
    Args:
        arguments: Search parameters
        runtime: The runtime environment
        
    Returns:
        Formatted search results with context
    """
    query = arguments["query"]
    search_path = arguments.get("path", ".")
    file_pattern = arguments.get("pattern")
    use_regex = arguments.get("regex", False)
    case_sensitive = arguments.get("case_sensitive", False)
    context_lines = min(arguments.get("context_lines", MAX_CONTEXT_LINES), 10)
    
    try:
        path = Path(search_path).resolve()
        
        if not path.exists():
            return f"Error: Path not found: {search_path}"
        
        # Compile regex pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        if use_regex:
            try:
                pattern = re.compile(query, flags)
            except re.error as e:
                return f"Error: Invalid regex pattern: {e}"
        else:
            # Escape literal string for regex matching
            pattern = re.compile(re.escape(query), flags)
        
        # Find matching files
        matches = []
        files_searched = 0
        
        if path.is_file():
            files_to_search = [path]
        else:
            files_to_search = _get_searchable_files(path, file_pattern)
        
        for filepath in files_to_search:
            files_searched += 1
            file_matches = _search_file(filepath, pattern, context_lines)
            if file_matches:
                matches.extend(file_matches)
            
            if len(matches) >= MAX_RESULTS:
                break
        
        if not matches:
            return f"No matches found for '{query}' in {files_searched} files"
        
        # Format results
        output = [f"Found {len(matches)} matches in {files_searched} files:\n"]
        
        for match in matches[:MAX_RESULTS]:
            output.append(_format_match(match))
        
        if len(matches) > MAX_RESULTS:
            output.append(f"\n... and {len(matches) - MAX_RESULTS} more matches (showing first {MAX_RESULTS})")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error searching code: {e}"


@register_tool(
    name="find_definition",
    description="Find the definition of a function, class, or variable. Searches for common definition patterns across languages (def, function, class, const, let, var, etc.).",
    schema=ToolSchema(
        properties={
            "name": {
                "type": "string",
                "description": "Name of the function, class, or variable to find",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in. Default: current directory",
            },
            "type": {
                "type": "string",
                "enum": ["function", "class", "variable", "any"],
                "description": "Type of definition to find. Default: 'any'",
            },
        },
        required=["name"],
    ),
    category="code",
)
async def find_definition(arguments: dict, runtime: "Runtime") -> str:
    """
    Find definition of a symbol.
    
    Args:
        arguments: Search parameters
        runtime: The runtime environment
        
    Returns:
        Definition location(s) with context
    """
    name = arguments["name"]
    search_path = arguments.get("path", ".")
    def_type = arguments.get("type", "any")
    
    # Build regex patterns for different definition types
    patterns = {
        "function": [
            rf"^\s*def\s+{re.escape(name)}\s*\(",           # Python
            rf"^\s*async\s+def\s+{re.escape(name)}\s*\(",   # Python async
            rf"^\s*function\s+{re.escape(name)}\s*\(",      # JavaScript
            rf"^\s*async\s+function\s+{re.escape(name)}\s*\(",  # JS async
            rf"^\s*{re.escape(name)}\s*[:=]\s*(?:async\s+)?function",  # JS assigned
            rf"^\s*{re.escape(name)}\s*[:=]\s*\([^)]*\)\s*=>",  # JS arrow
            rf"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:async\s+)?{re.escape(name)}\s*\(",  # JS/TS method
            rf"^\s*func\s+{re.escape(name)}\s*\(",          # Go
            rf"^\s*(?:public|private|protected)\s+.*\s+{re.escape(name)}\s*\(",  # Java/C#
        ],
        "class": [
            rf"^\s*class\s+{re.escape(name)}\b",            # Python/JS/TS
            rf"^\s*(?:abstract\s+)?class\s+{re.escape(name)}\b",  # Java/C#
            rf"^\s*interface\s+{re.escape(name)}\b",        # TS/Java
            rf"^\s*type\s+{re.escape(name)}\s*=",           # TS type alias
            rf"^\s*struct\s+{re.escape(name)}\b",           # Go/Rust
        ],
        "variable": [
            rf"^\s*{re.escape(name)}\s*=",                  # Python/Ruby
            rf"^\s*(?:const|let|var)\s+{re.escape(name)}\b",  # JavaScript
            rf"^\s*(?:const|let|var)\s+{re.escape(name)}\s*:",  # TypeScript
            rf"^\s*(?:var|val)\s+{re.escape(name)}\b",      # Kotlin/Scala
            rf"^\s*{re.escape(name)}\s*:=",                 # Go
        ],
    }
    
    # Select patterns based on type
    if def_type == "any":
        selected_patterns = []
        for p_list in patterns.values():
            selected_patterns.extend(p_list)
    else:
        selected_patterns = patterns.get(def_type, [])
    
    if not selected_patterns:
        return f"Error: Unknown definition type '{def_type}'"
    
    # Combine patterns
    combined_pattern = "|".join(f"({p})" for p in selected_patterns)
    
    try:
        pattern = re.compile(combined_pattern, re.MULTILINE)
        path = Path(search_path).resolve()
        
        if not path.exists():
            return f"Error: Path not found: {search_path}"
        
        matches = []
        files_searched = 0
        
        for filepath in _get_searchable_files(path, None):
            files_searched += 1
            file_matches = _search_file(filepath, pattern, context_lines=5)
            if file_matches:
                matches.extend(file_matches)
            
            if len(matches) >= 10:
                break
        
        if not matches:
            return f"No definition found for '{name}' ({def_type}) in {files_searched} files"
        
        output = [f"Found {len(matches)} definition(s) for '{name}':\n"]
        for match in matches[:10]:
            output.append(_format_match(match))
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error finding definition: {e}"


@register_tool(
    name="list_functions",
    description="List all function/method definitions in a file or directory. Useful for understanding code structure.",
    schema=ToolSchema(
        properties={
            "path": {
                "type": "string",
                "description": "File or directory to analyze",
            },
            "pattern": {
                "type": "string",
                "description": "File glob pattern (e.g., '*.py'). Default: auto-detect",
            },
        },
        required=["path"],
    ),
    category="code",
)
async def list_functions(arguments: dict, runtime: "Runtime") -> str:
    """
    List function definitions in files.
    
    Args:
        arguments: Search parameters
        runtime: The runtime environment
        
    Returns:
        List of functions with file and line numbers
    """
    search_path = arguments["path"]
    file_pattern = arguments.get("pattern")
    
    # Patterns for function definitions
    func_patterns = [
        (r"^\s*def\s+(\w+)\s*\(", "python"),
        (r"^\s*async\s+def\s+(\w+)\s*\(", "python"),
        (r"^\s*function\s+(\w+)\s*\(", "javascript"),
        (r"^\s*async\s+function\s+(\w+)\s*\(", "javascript"),
        (r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", "javascript"),
        (r"^\s*(\w+)\s*[:=]\s*(?:async\s+)?function", "javascript"),
        (r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>", "javascript"),
        (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)\s*[:{]", "typescript"),
        (r"^\s*func\s+(\w+)\s*\(", "go"),
        (r"^\s*(?:public|private|protected)\s+.*\s+(\w+)\s*\([^)]*\)\s*{", "java"),
    ]
    
    combined = "|".join(f"(?:{p})" for p, _ in func_patterns)
    pattern = re.compile(combined, re.MULTILINE)
    
    try:
        path = Path(search_path).resolve()
        
        if not path.exists():
            return f"Error: Path not found: {search_path}"
        
        results: Dict[str, List[Tuple[int, str]]] = {}
        
        if path.is_file():
            files_to_search = [path]
        else:
            files_to_search = _get_searchable_files(path, file_pattern)
        
        for filepath in files_to_search:
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                
                for i, line in enumerate(lines, 1):
                    match = pattern.search(line)
                    if match:
                        # Find the first non-None group (function name)
                        func_name = next((g for g in match.groups() if g), None)
                        if func_name:
                            rel_path = str(filepath.relative_to(path) if path.is_dir() else filepath.name)
                            if rel_path not in results:
                                results[rel_path] = []
                            results[rel_path].append((i, func_name))
            except Exception:
                continue
        
        if not results:
            return f"No functions found in {search_path}"
        
        output = [f"Functions in {search_path}:\n"]
        
        for filepath, funcs in sorted(results.items()):
            output.append(f"\n{filepath}:")
            for line_num, func_name in funcs:
                output.append(f"  L{line_num}: {func_name}()")
        
        total = sum(len(f) for f in results.values())
        output.insert(1, f"Found {total} functions in {len(results)} files")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error listing functions: {e}"


def _get_searchable_files(path: Path, pattern: Optional[str]) -> List[Path]:
    """Get list of searchable files, excluding binary and hidden files."""
    files = []
    
    # File extensions to search
    code_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".rs", ".swift", ".kt", ".scala",
        ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".xml", ".html", ".htm", ".css", ".scss", ".sass",
        ".sql", ".graphql", ".md", ".txt", ".env", ".gitignore",
    }
    
    # Directories to skip
    skip_dirs = {
        ".git", ".svn", ".hg", "node_modules", "__pycache__", ".pytest_cache",
        "venv", ".venv", "env", ".env", "dist", "build", "target", ".idea",
        ".vscode", "coverage", ".tox", "eggs", "*.egg-info",
    }
    
    for root, dirs, filenames in os.walk(path):
        # Skip hidden and common non-code directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        
        for filename in filenames:
            filepath = Path(root) / filename
            
            # Skip hidden files
            if filename.startswith("."):
                continue
            
            # Apply glob pattern if specified
            if pattern and not filepath.match(pattern):
                continue
            
            # Check extension
            if filepath.suffix.lower() in code_extensions or not filepath.suffix:
                files.append(filepath)
    
    return files


def _search_file(
    filepath: Path, 
    pattern: re.Pattern, 
    context_lines: int
) -> List[dict]:
    """Search a single file for pattern matches."""
    matches = []
    
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            if pattern.search(line):
                # Get context
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                
                context = []
                for j in range(start, end):
                    prefix = "→ " if j == i else "  "
                    context.append((j + 1, prefix, lines[j]))
                
                matches.append({
                    "file": str(filepath),
                    "line": i + 1,
                    "match": line.strip(),
                    "context": context,
                })
    except Exception:
        pass
    
    return matches


def _format_match(match: dict) -> str:
    """Format a search match for display."""
    output = [f"\n{'─' * 50}"]
    output.append(f"📄 {match['file']}:{match['line']}")
    output.append("")
    
    for line_num, prefix, text in match["context"]:
        output.append(f"{line_num:4d} {prefix}{text}")
    
    return "\n".join(output)
