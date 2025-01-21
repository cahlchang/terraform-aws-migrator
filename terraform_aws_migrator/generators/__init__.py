# terraform_aws_migrator/generators/__init__.py

import logging
import pkgutil
import importlib
from pathlib import Path
from .base import HCLGenerator, HCLGeneratorRegistry, register_generator

logger = logging.getLogger(__name__)


def load_generators():
    """Dynamically load all generator modules from all subdirectories"""
    logger.debug("Starting to load generator modules")

    # Get the directory containing the generators
    generators_dir = Path(__file__).parent

    def load_from_directory(directory: Path, package_prefix: str):
        """Recursively load modules from a directory"""
        if not directory.exists():
            return

        # Load modules from current directory
        for module_info in pkgutil.iter_modules([str(directory)]):
            # Skip __init__.py and base.py
            if module_info.name in ['__init__', 'base']:
                continue

            module_name = f"{package_prefix}.{module_info.name}"
            try:
                importlib.import_module(module_name)
                logger.debug(f"Successfully loaded module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load generator module {module_name}: {str(e)}")

        # Recursively process subdirectories
        for item in directory.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                subpackage = f"{package_prefix}.{item.name}"
                load_from_directory(item, subpackage)

    # Start loading from the root generators directory
    load_from_directory(generators_dir, __package__)

    # List all registered generators after loading
    registered_types = list(HCLGeneratorRegistry._generators.keys())
    logger.debug(f"Currently registered generator types: {registered_types}")


# Initialize registry and load generators
load_generators()

__all__ = ["HCLGenerator", "HCLGeneratorRegistry", "register_generator"]
