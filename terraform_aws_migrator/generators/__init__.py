# terraform_aws_migrator/generators/__init__.py

import logging
from .base import HCLGenerator, HCLGeneratorRegistry, register_generator

logger = logging.getLogger(__name__)

logger.debug("Initializing generators package")

# Explicitly import aws_iam subpackage
from . import aws_iam
logger.debug("Imported aws_iam subpackage")

# Initialize registry
HCLGeneratorRegistry._initialize()
logger.debug("Registry initialization complete")

# List registered generators
registered_types = list(HCLGeneratorRegistry._generators.keys())
logger.debug(f"Currently registered generator types: {registered_types}")

__all__ = ['HCLGenerator', 'HCLGeneratorRegistry', 'register_generator']
