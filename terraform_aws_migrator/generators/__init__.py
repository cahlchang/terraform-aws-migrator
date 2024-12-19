# terraform_aws_migrator/generators/__init__.py

__all__ = ['HCLGenerator', 'HCLGeneratorRegistry', 'register_generator']


# terraform_aws_migrator/generators/__init__.py
from pathlib import Path
import importlib.util
import logging
from typing import Dict, Type
from .base import HCLGenerator, HCLGeneratorRegistry, register_generator

logger = logging.getLogger(__name__)

def load_generators() -> None:
    """Load all generator modules from the generators directory"""
    generators_dir = Path(__file__).parent
    
    # Recursively find all .py files
    for py_file in generators_dir.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue
            
        module_name = py_file.stem
        if module_name == "base":
            continue
            
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                logger.debug(f"Loaded generator module: {module_name}")
        except Exception as e:
            logger.error(f"Failed to load generator {module_name}: {e}")

# Initialize generators when this module is imported
load_generators()

class RegistryManager:
    """Manages the HCL Generator Registry"""
    
    @classmethod
    def get_generator(cls, resource_type: str) -> Type[HCLGenerator]:
        """Get generator for resource type"""
        generator = HCLGeneratorRegistry.get_generator(resource_type)
        if not generator:
            logger.error(f"No generator found for {resource_type}")
        return generator
        
    @classmethod
    def is_supported(cls, resource_type: str) -> bool:
        """Check if resource type is supported"""
        return HCLGeneratorRegistry.is_supported(resource_type)

    @classmethod
    def list_supported_types(cls) -> Dict[str, str]:
        """List all supported resource types"""
        return HCLGeneratorRegistry.list_supported_types()

