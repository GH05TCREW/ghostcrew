"""Dynamic tool loader for PentestAgent."""

import importlib
import sys
from pathlib import Path
from typing import List, Optional

from .registry import get_all_tools


def discover_tools(tools_dir: Optional[Path] = None) -> List[str]:
    """
    Discover all tool modules in the tools directory.

    Args:
        tools_dir: Path to tools directory. Defaults to package tools dir.

    Returns:
        List of discovered tool module names
    """
    if tools_dir is None:
        tools_dir = Path(__file__).parent

    discovered = []

    for item in tools_dir.iterdir():
        # Skip non-tool items
        if item.name.startswith("_"):
            continue
        if item.name in ("registry.py", "executor.py", "loader.py"):
            continue

        # Check if it's a tool module
        if item.is_dir() and (item / "__init__.py").exists():
            discovered.append(item.name)
        elif item.suffix == ".py":
            discovered.append(item.stem)

    return discovered


def load_tool_module(module_name: str, tools_dir: Optional[Path] = None) -> bool:
    """
    Load a tool module by name.

    Args:
        module_name: Name of the tool module to load
        tools_dir: Path to tools directory

    Returns:
        True if loaded successfully, False otherwise
    """
    if tools_dir is None:
        tools_dir = Path(__file__).parent

    try:
        # Build the full module path
        full_module_name = f"pentestagent.tools.{module_name}"

        # Check if already loaded
        if full_module_name in sys.modules:
            return True

        # Try to import the module
        importlib.import_module(full_module_name)
        return True

    except ImportError as e:
        print(f"Warning: Failed to load tool module '{module_name}': {e}")
        return False
    except Exception as e:
        print(f"Warning: Error loading tool module '{module_name}': {e}")
        return False


def load_all_tools(tools_dir: Optional[Path] = None) -> List[str]:
    """
    Discover and load all tool modules.

    Args:
        tools_dir: Path to tools directory

    Returns:
        List of successfully loaded tool module names
    """
    discovered = discover_tools(tools_dir)
    loaded = []

    for module_name in discovered:
        if load_tool_module(module_name, tools_dir):
            loaded.append(module_name)

    return loaded


def get_tool_info() -> List[dict]:
    """
    Get information about all registered tools.

    Returns:
        List of tool info dictionaries
    """
    tools = get_all_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "enabled": tool.enabled,
            "parameters": (
                list(tool.schema.properties.keys()) if tool.schema.properties else []
            ),
        }
        for tool in tools
    ]


def reload_tools():
    """Reload all tool modules."""
    from .registry import clear_tools

    # Clear existing tools
    clear_tools()

    # Unload tool modules from sys.modules
    to_remove = [
        name
        for name in sys.modules
        if name.startswith("pentestagent.tools.")
        and name
        not in (
            "pentestagent.tools",
            "pentestagent.tools.registry",
            "pentestagent.tools.executor",
            "pentestagent.tools.loader",
        )
    ]

    for name in to_remove:
        del sys.modules[name]

    # Reload all tools
    return load_all_tools()
