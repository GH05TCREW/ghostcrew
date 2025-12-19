import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base_playbook import BasePlaybook

# Registry of available playbooks
PLAYBOOKS: Dict[str, Type[BasePlaybook]] = {}


def _discover_playbooks():
    """Dynamically discover and register playbooks in the current package."""
    package_dir = Path(__file__).parent

    # Iterate over all modules in the current package
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        # Skip base_playbook to avoid circular imports or registering the base class
        if module_name == "base_playbook":
            continue

        try:
            # Import the module
            module = importlib.import_module(f".{module_name}", package=__package__)

            # Find all classes in the module that inherit from BasePlaybook
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePlaybook) and obj is not BasePlaybook:
                    # Register the playbook using its defined name
                    if hasattr(obj, "name"):
                        PLAYBOOKS[obj.name] = obj
        except Exception as e:
            print(f"Error loading playbook module {module_name}: {e}")


# Run discovery on import
_discover_playbooks()


def get_playbook(name: str) -> BasePlaybook:
    """Get a playbook instance by name."""
    if name not in PLAYBOOKS:
        raise ValueError(
            f"Playbook '{name}' not found. Available: {list(PLAYBOOKS.keys())}"
        )
    return PLAYBOOKS[name]()


def list_playbooks() -> list[str]:
    """List available playbook names."""
    return list(PLAYBOOKS.keys())
