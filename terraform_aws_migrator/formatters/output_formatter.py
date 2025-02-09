# terraform_aws_migrator/formatters/output_formatter.py

import json
from typing import Dict, List, Any, Tuple
import logging
from ..collectors.base import registry

logger = logging.getLogger(__name__)


def _split_resource_type(resource_type: str) -> Tuple[str, str]:
    """
    Separate module path and resource type

    Args:
        resource_type: Resource type (e.g., 'module.example_module.aws_instance')

    Returns:
        Tuple[str, str]: (module path, resource type)
        e.g., ('module.example_module', 'aws_instance')
    """
    parts = resource_type.split('.')
    if len(parts) > 2 and parts[0] == 'module':
        module_path = '.'.join(parts[:-1])
        base_type = parts[-1]
        return module_path, base_type
    return '', resource_type


def format_output(resources: Dict[str, List[Dict[str, Any]]], output_format: str = "text") -> str:
    """
    Format the output of unmanaged AWS resources

    Args:
        resources: Dictionary containing unmanaged resources by service
        output_format: Desired output format ("text" or "json")

    Returns:
        Formatted string containing the unmanaged resources
    """
    try:
        if output_format == "json":
            return json.dumps(resources, indent=2, default=str)

        if not resources:
            return "No unmanaged resources found."

        output = []
        output.append("\nUnmanaged AWS Resources:")
        output.append("=" * 40)

        # Count total unmanaged resources
        total_unmanaged = sum(
            sum(1 for r in res_list if not r.get("managed", False))
            for res_list in resources.values()
        )

        # Resource Summary
        output.append("\nResource Summary:")
        output.append(f"Total Unmanaged Resources: {total_unmanaged}")
        output.append("")

        # Create collectors map for resource type lookups
        collectors: Dict[str, Any] = {
            collector_cls.get_service_name(): collector_cls
            for collector_cls in registry
        }

        # Group resources by type
        resource_counts: Dict[str, List[Dict[str, Any]]] = {}
        for service_name, service_resources in resources.items():
            collector_cls = collectors.get(service_name)
            if not collector_cls:
                continue

            for resource in service_resources:
                resource_type = resource.get("type", "unknown")
                module_path, base_type = _split_resource_type(resource_type)
                
                # Use base resource type as key
                if base_type not in resource_counts:
                    resource_counts[base_type] = {
                        "services": set(),  # Services this resource type belongs to
                        "resources": [],
                        "modules": set()  # Modules where this resource type is used
                    }
                
                # Add service name
                resource_counts[base_type]["services"].add(service_name)
                # Add module path if it exists
                if module_path:
                    resource_counts[base_type]["modules"].add(module_path)
                # Add resource
                resource_counts[base_type]["resources"].append(resource)

        # Resources by Type
        if resource_counts:
            output.append("Resources by Type:")
            for base_type, resource_data in sorted(resource_counts.items()):
                resources_list = resource_data["resources"]
                services = resource_data["services"]
                modules = resource_data["modules"]
                
                # Get resource type display name using collector from any service
                display_name = base_type
                for service_name in services:
                    collector_cls = collectors.get(service_name)
                    if collector_cls:
                        display_name = collector_cls.get_type_display_name(base_type)
                        break
                
                # Count managed state
                managed_count = sum(1 for r in resources_list if r.get("managed", False))
                unmanaged_count = len(resources_list) - managed_count
                
                if unmanaged_count > 0 or managed_count > 0:
                    # Display with module information
                    if modules:
                        module_info = f" (in modules: {', '.join(sorted(modules))})"
                    else:
                        module_info = ""
                    output.append(f"- Found {unmanaged_count} unmanaged, {managed_count} managed {display_name}{module_info}")

        # Detailed Resources Section
        if output_format == "text":
            output.append("\nResource List:")
            for base_type, resource_data in sorted(resource_counts.items()):
                resources_list = resource_data["resources"]
                services = resource_data["services"]
                
                # Get resource type display name using collector from any service
                display_name = base_type
                for service_name in services:
                    collector_cls = collectors.get(service_name)
                    if collector_cls:
                        display_name = collector_cls.get_type_display_name(base_type)
                        break

                # Filter unmanaged resources
                unmanaged_resources = [r for r in resources_list if not r.get("managed", False)]
                if unmanaged_resources:  # Only show resource type if it has unmanaged resources
                    output.append(f"\n{display_name}:")
                    for resource in unmanaged_resources:
                        resource_id = resource.get("id", "N/A")
                        # Try to get name from details or tags
                        name = None
                        details = resource.get("details", {})
                        if details and "Name" in details:
                            name = details["Name"]
                        else:
                            tags = resource.get("tags", {})
                            if isinstance(tags, dict) and "Name" in tags:
                                name = tags["Name"]
                            elif isinstance(tags, list):
                                for tag in tags:
                                    if isinstance(tag, dict) and tag.get("Key") == "Name":
                                        name = tag.get("Value")
                                        break
                        
                        if name:
                            output.append(f"  - {name} ({resource_id})")
                        else:
                            output.append(f"  - {resource_id}")

        return "\n".join(output)

    except Exception as e:
        logger.exception("Error formatting output")
        return f"Error formatting output: {str(e)}"
