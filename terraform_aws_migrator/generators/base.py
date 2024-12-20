# terraform_aws_migrator/generators/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
import importlib
import os
import pkgutil
import logging

logger = logging.getLogger(__name__)

class HCLGenerator(ABC):
    """Base class for HCL generators"""
    
    @classmethod
    @abstractmethod
    def resource_type(cls) -> str:
        """Return the resource type this generator handles"""
        pass

    @abstractmethod
    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for the given resource"""
        pass

class HCLGeneratorRegistry:
    """Registry for HCL generators"""
    
    _generators: Dict[str, Type[HCLGenerator]] = {}
    _initialized = False

    @classmethod
    def register(cls, generator_class: Type[HCLGenerator]) -> Type[HCLGenerator]:
        """Register a generator class"""
        resource_type = generator_class.resource_type()
        cls._generators[resource_type] = generator_class
        logger.debug(f"Registered generator for {resource_type}")
        return generator_class

    @classmethod
    def get_generator(cls, resource_type: str) -> Optional[HCLGenerator]:
        """Get a generator instance for the given resource type"""
        if not cls._initialized:
            cls._initialize()
        
        generator_class = cls._generators.get(resource_type)
        if generator_class:
            return generator_class()
        return None

    @classmethod
    def is_supported(cls, resource_type: str) -> bool:
        """Check if a resource type is supported"""
        if not cls._initialized:
            cls._initialize()
            
        return resource_type in cls._generators

    @classmethod
    def _initialize(cls) -> None:
        """Initialize the registry by discovering and loading all generators"""
        if cls._initialized:
            logger.debug("Registry already initialized")
            return
            
        logger.debug("Starting registry initialization")

        # Get the generators directory path
        generators_dir = os.path.dirname(__file__)
        
        # Function to recursively load modules from a directory
        def load_modules_from_dir(dir_path: str, package_prefix: str) -> None:
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                
                # Skip __pycache__ and files starting with _
                if item.startswith('_') or item == '__pycache__':
                    continue
                
                if os.path.isdir(item_path):
                    # It's a subdirectory - recurse into it
                    subpackage = f"{package_prefix}.{item}"
                    load_modules_from_dir(item_path, subpackage)
                    
                elif item.endswith('.py'):
                    # It's a Python file - try to import it
                    module_name = f"{package_prefix}.{item[:-3]}"  # Remove .py extension
                    try:
                        if module_name != "terraform_aws_migrator.generators.base":  # Skip base.py
                            importlib.import_module(module_name)
                            logger.debug(f"Successfully loaded module: {module_name}")
                    except Exception as e:
                        logger.debug(f"Failed to load generator module {module_name}: {e}")

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


def register_generator(generator_class: Type[HCLGenerator]) -> Type[HCLGenerator]:
    """Decorator to register a generator class"""
    return HCLGeneratorRegistry.register(generator_class)
