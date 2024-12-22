# terraform_aws_migrator/generators/aws_iam/__init__.py

import os
import importlib
import logging
from typing import List

logger = logging.getLogger(__name__)


def _load_modules() -> List[str]:
    """Dynamically load all Python modules in the current directory"""
    current_dir = os.path.dirname(__file__)
    loaded_modules = []

    for filename in os.listdir(current_dir):
        if (
            filename.startswith("_")
            or not filename.endswith(".py")
            or filename == "__init__.py"
        ):
            continue

        module_name = filename[:-3]
        full_module_path = f"{__package__}.{module_name}"

        try:
            importlib.import_module(full_module_path)
            loaded_modules.append(module_name)
        except Exception as e:
            logger.error(
                f"Failed to load IAM generator module {full_module_path}: {str(e)}"
            )

    return loaded_modules


# Load all modules when this package is imported
loaded_modules = _load_modules()

# Export loaded module names
__all__ = loaded_modules
