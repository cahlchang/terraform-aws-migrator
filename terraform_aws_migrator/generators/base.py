# terraform_aws_migrator/generators/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, Union
import importlib
import os
import pkgutil
import logging

logger = logging.getLogger(__name__)


class HCLGenerator(ABC):
    """Base class for HCL generators"""

    def __init__(self, module_prefix: Optional[str] = None, state_reader: Optional[Any] = None):
        """
        Initialize the generator

        Args:
            module_prefix (str, optional): Module prefix for import commands
            state_reader (TerraformStateReader, optional): State reader instance
        """
        self.module_prefix = module_prefix
        self.state_reader = state_reader
        self.managed_resources = {}
        if state_reader:
            self.managed_resources = state_reader.get_managed_resources("")

    def is_resource_managed(self, resource_type: str, resource_name: str) -> bool:
        """Check if a resource is managed by Terraform"""
        if not self.state_reader:
            return False

        for resource in self.managed_resources.values():
            if resource.get("type") == resource_type and resource.get("id") == resource_name:
                return True
        return False

    @classmethod
    @abstractmethod
    def resource_type(cls) -> str:
        """Return the resource type this generator handles"""
        pass

    @abstractmethod
    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for the given resource"""
        pass

    def get_import_prefix(self) -> str:
        """
        Get the module prefix for import commands

        Returns:
            str: Module prefix string (e.g., "module.my_module") or empty string
        """
        return f"module.{self.module_prefix}" if self.module_prefix else ""


class HCLGeneratorRegistry:
    """Registry for HCL generators"""

    _generators: Dict[str, Type[HCLGenerator]] = {}
    _initialized = False

    @classmethod
    def register(cls, generator_class: Type[HCLGenerator]) -> Type[HCLGenerator]:
        """Register a generator class"""
        resource_type = generator_class.resource_type()
        cls._generators[resource_type] = generator_class
        return generator_class

    @classmethod
    def get_generator(
        cls, resource_type: str, module_prefix: Optional[str] = None, state_reader: Optional[Any] = None
    ) -> Optional[HCLGenerator]:
        """
        Get a generator instance for the given resource type

        Args:
            resource_type (str): AWS resource type
            module_prefix (str, optional): Module prefix for import commands
            state_reader (TerraformStateReader, optional): State reader instance

        Returns:
            Optional[HCLGenerator]: Generator instance if supported, None otherwise
        """
        if not cls._initialized:
            cls._initialize()

        generator_class = cls._generators.get(resource_type)
        if generator_class:
            return generator_class(module_prefix=module_prefix, state_reader=state_reader)
        return None

    @classmethod
    def is_supported(cls, resource_type: str) -> bool:
        """
        Check if a resource type or category is supported
        Args:
            resource_type (str): Resource type (e.g., aws_s3_bucket) or category (e.g., s3)
        """
        if not cls._initialized:
            cls._initialize()

        # 完全なリソースタイプの場合
        if resource_type in cls._generators:
            return True

        # カテゴリの場合（例：s3）
        # そのカテゴリに属する任意のリソースタイプが登録されているかチェック
        for registered_type in cls._generators.keys():
            if registered_type.startswith(f"aws_{resource_type}_"):
                return True

        return False

    @classmethod
    def get_generators_for_category(cls, category: str) -> Dict[str, Type[HCLGenerator]]:
        """Get all generators for a given category"""
        if not cls._initialized:
            cls._initialize()

        generators = {
            resource_type: generator_class
            for resource_type, generator_class in cls._generators.items()
            if resource_type.startswith(f"aws_{category}_")
        }

        if not generators:
            logger.warning(f"No generators found for category: {category}")
        
        return generators

    @classmethod
    def _initialize(cls) -> None:
        """Initialize the registry by discovering and loading all generators"""
        if cls._initialized:
            logger.debug("Registry already initialized")
            return

        # Get the generators directory path
        generators_dir = os.path.dirname(__file__)

        # Function to recursively load modules from a directory
        def load_modules_from_dir(dir_path: str, package_prefix: str) -> None:
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)

                # Skip __pycache__ and files starting with _
                if item.startswith("_") or item == "__pycache__":
                    continue

                if os.path.isdir(item_path):
                    # It's a subdirectory - recurse into it
                    subpackage = f"{package_prefix}.{item}"
                    load_modules_from_dir(item_path, subpackage)

                elif item.endswith(".py"):
                    # It's a Python file - try to import it
                    module_name = (
                        f"{package_prefix}.{item[:-3]}"  # Remove .py extension
                    )
                    try:
                        if (
                            module_name != "terraform_aws_migrator.generators.base"
                        ):  # Skip base.py
                            module = importlib.import_module(module_name)
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                    except Exception as e:
                        logger.error(
                            f"Failed to load generator module {module_name}: {str(e)}"
                        )

        # Load all modules from the generators directory
        load_modules_from_dir(generators_dir, "terraform_aws_migrator.generators")

        if not cls._generators:
            logger.warning("No generators were registered")
        else:
            logger.debug(f"Registered generators: {list(cls._generators.keys())}")

        cls._initialized = True

    @classmethod
    def list_supported_types(cls) -> Dict[str, str]:
        """List all supported resource types"""
        if not cls._initialized:
            cls._initialize()

        return {
            resource_type: generator_class.__doc__ or ""
            for resource_type, generator_class in cls._generators.items()
        }

    @classmethod
    @abstractmethod
    def resource_type(cls) -> str:
        """Return the resource type this generator handles"""
        pass

    @abstractmethod
    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for the given resource"""
        pass

    @abstractmethod
    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate Terraform import command for the given resource"""
        pass


def register_generator(generator_class: Type[HCLGenerator]) -> Type[HCLGenerator]:
    """Decorator to register a generator class"""
    return HCLGeneratorRegistry.register(generator_class)
