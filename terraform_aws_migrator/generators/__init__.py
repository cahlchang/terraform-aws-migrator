# terraform_aws_migrator/generators/__init__.py

import logging
import pkgutil
import importlib
from pathlib import Path
from .base import HCLGenerator, HCLGeneratorRegistry, register_generator

logger = logging.getLogger(__name__)


def load_generators():
    """Explicitly load all generator modules"""
    logger.debug("Starting to load generator modules")

    # Get the directory containing the generators
    generators_dir = Path(__file__).parent

    # Define subdirectories to load generators from
    generator_subdirs = ["aws_iam", "aws_network"]

    for subdir_name in generator_subdirs:
        subdir_path = generators_dir / subdir_name
        if subdir_path.exists():
            for module_info in pkgutil.iter_modules([str(subdir_path)]):
                module_name = f"{__package__}.{subdir_name}.{module_info.name}"
                try:
                    importlib.import_module(module_name)
                    logger.debug(f"Successfully loaded generator module: {module_name}")
                except Exception as e:
                    logger.error(
                        f"Failed to load generator module {module_name}: {str(e)}"
                    )
        else:
            logger.warning(f"Generator directory not found at {subdir_path}")

    # List all registered generators after loading
    registered_types = list(HCLGeneratorRegistry._generators.keys())
    logger.debug(f"Currently registered generator types: {registered_types}")


# Initialize registry and load generators
load_generators()

__all__ = ["HCLGenerator", "HCLGeneratorRegistry", "register_generator"]
