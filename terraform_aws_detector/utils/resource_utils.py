# terraform_aws_detector/utils/resource_utils.py

import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any
from rich.console import Console

from terraform_aws_detector.collectors.base import ResourceCollector


def get_collectors_info() -> Dict[str, List[Dict[str, Any]]]:
    """Get information about all available collectors grouped by category"""
    collectors_dir = Path(__file__).parent.parent / "collectors"
    categories = {}

    # Find all collector modules (aws_*.py files)
    for file_path in collectors_dir.glob("aws_*.py"):
        if file_path.name == "aws_base.py":
            continue

        # Get category from filename (aws_compute.py -> Compute)
        category = file_path.stem.replace("aws_", "").title()

        # Import the module
        module_name = f"terraform_aws_detector.collectors.{file_path.stem}"
        module = importlib.import_module(module_name)

        # Find all collector classes in the module
        collectors = []
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, ResourceCollector)
                and obj != ResourceCollector
            ):
                service_name = obj.get_service_name()
                resource_types = obj.get_resource_types()
                collectors.extend(
                    [
                        {
                            "type": resource_type,
                            "description": description,
                            "service": service_name,
                        }
                        for resource_type, description in resource_types.items()
                    ]
                )

        if collectors:
            categories[category] = collectors

    return categories


def show_supported_resources():
    """Display information about supported resource types"""
    console = Console()
    categories = get_collectors_info()

    console.print("\n[bold cyan]Supported AWS Resource Types[/bold cyan]")
    console.print("These resources can be detected by terraform-aws-detector:\n")

    for category, resources in sorted(categories.items()):
        console.print(f"[bold yellow]{category}[/bold yellow]")
        for resource in sorted(resources, key=lambda x: x["type"]):
            console.print(f"  • {resource['type']}: {resource['description']}")
        console.print("")
