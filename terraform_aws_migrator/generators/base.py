# terraform_aws_migrator/generators/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
import importlib
import pkgutil
import logging

logger = logging.getLogger(__name__)


class HCLGenerator(ABC):
    """Base class for HCL code generators"""

    @abstractmethod
    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL code for the given resource"""
        pass

    @classmethod
    @abstractmethod
    def resource_type(cls) -> str:
        """Return the AWS resource type this generator handles"""
        pass


class HCLGeneratorRegistry:
    """Registry for HCL generators"""

    _generators: Dict[str, Type[HCLGenerator]] = {}

    @classmethod
    def register(cls, generator_class: Type[HCLGenerator]):
        """Register a generator class"""
        resource_type = generator_class.resource_type()
        cls._generators[resource_type] = generator_class
        logger.debug(f"Registered HCL generator for {resource_type}")

    @classmethod
    def get_generator(cls, resource_type: str) -> Optional[HCLGenerator]:
        """Get generator instance for resource type"""
        generator_class = cls._generators.get(resource_type)
        if generator_class:
            return generator_class()
        return None

    @classmethod
    def is_supported(cls, resource_type: str) -> bool:
        """Check if a resource type is supported"""
        return resource_type in cls._generators


def register_generator(generator_class: Type[HCLGenerator]):
    """Decorator to register an HCL generator"""
    HCLGeneratorRegistry.register(generator_class)
    return generator_class


def load_generators():
    """Load all generator modules"""
    import terraform_aws_migrator.generators as generators_package

    package_path = generators_package.__path__
    for _, name, _ in pkgutil.iter_modules(package_path):
        if name != "base":  # Skip the base module
            try:
                importlib.import_module(f".{name}", "terraform_aws_migrator.generators")
                logger.debug(f"Loaded generator module: {name}")
            except Exception as e:
                logger.error(f"Error loading generator module {name}: {str(e)}")
