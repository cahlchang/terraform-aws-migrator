# terraform_aws_migrator/collectors/__init__.py

import importlib
from pathlib import Path
from .base import ResourceCollector, register_collector


def _import_collectors():
    current_dir = Path(__file__).parent

    for file_path in current_dir.glob("aws_*.py"):
        module_name = f".{file_path.stem}"
        try:
            importlib.import_module(
                module_name, package="terraform_aws_migrator.collectors"
            )
        except ImportError as e:
            print(f"Warning: Failed to import {module_name}: {e}")

    for dir_path in current_dir.glob("aws_*"):
        if not dir_path.is_dir():
            continue

        for file_path in dir_path.glob("*.py"):
            if file_path.name == "__init__.py":
                continue

            relative_path = file_path.relative_to(current_dir)
            module_name = f".{relative_path.parent.name}.{file_path.stem}"
            try:
                importlib.import_module(
                    module_name, package="terraform_aws_migrator.collectors"
                )
            except ImportError as e:
                print(f"Warning: Failed to import {module_name}: {e}")


_import_collectors()

__all__ = ["ResourceCollector", "register_collector"]
