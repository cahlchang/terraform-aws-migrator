# terraform_aws_migrator/formatters/output_formatter.py

import json
from typing import Dict, List, Any
import logging
from ..collectors.base import registry

logger = logging.getLogger(__name__)

def format_output(resources: Dict[str, Dict[str, List[Dict[str, Any]]]], output_format: str = "text") -> str:
    """
    Format the output of the AWS resource audit
    
    Args:
        resources: Dictionary containing both managed and unmanaged resources
        output_format: Desired output format ("text" or "json")
        
    Returns:
        Formatted string containing the audit results
    """
    try:
        if output_format == "json":
            return json.dumps(resources, indent=2, default=str)

        if not resources:
            return "No resources found."

        output = []
        output.append("\nAWS Resources Audit Report:")
        output.append("=" * 40)

        # Get managed and unmanaged resources
        managed_resources = resources.get('managed', {})
        unmanaged_resources = resources.get('unmanaged', {})

        # Count total resources
        total_managed = sum(len(res_list) for res_list in managed_resources.values())
        total_unmanaged = sum(len(res_list) for res_list in unmanaged_resources.values())
        total_resources = total_managed + total_unmanaged

        # Resource Summary
        output.append("\nResource Summary:")
        output.append(f"Total Resources: {total_resources}")
        output.append(f"Managed by Terraform: {total_managed}")
        output.append(f"Not Managed by Terraform: {total_unmanaged}")
        output.append(f"Management Ratio: {(total_managed / total_resources * 100):.1f}% managed")

        # Create collectors map for resource type lookups
        collectors = {
            collector_cls.get_service_name(): collector_cls
            for collector_cls in registry
        }

        # Group unmanaged resources by type
        resource_counts = {}
        for service_name, service_resources in unmanaged_resources.items():
            collector_cls = collectors.get(service_name)
            if not collector_cls:
                continue

            for resource in service_resources:
                resource_type = resource.get("type", "unknown")
                full_type = f"{service_name}.{resource_type}"
                if full_type not in resource_counts:
                    resource_counts[full_type] = []
                resource_counts[full_type].append(resource)

        # Unmanaged Resources Summary
        if resource_counts:
            output.append("\nUnmanaged Resources by Type:")
            for full_type, resources_list in sorted(resource_counts.items()):
                service_name, resource_type = full_type.split(".", 1)
                collector_cls = collectors.get(service_name)
                
                if collector_cls:
                    display_name = collector_cls.get_type_display_name(resource_type)
                else:
                    display_name = full_type
                    
                count = len(resources_list)
                output.append(f"- Found {count} unmanaged {display_name}")

        # Detailed Resources Section
        if output_format == "text" and resource_counts:
            output.append("\nDetailed Resources:")
            for full_type, resources_list in sorted(resource_counts.items()):
                service_name, resource_type = full_type.split(".", 1)
                collector_cls = collectors.get(service_name)

                if collector_cls:
                    display_name = collector_cls.get_type_display_name(resource_type)
                else:
                    display_name = full_type

                output.append(f"\n{display_name}:")

                for resource in resources_list:
                    resource_id = resource.get("id", "N/A")
                    resource_arn = resource.get("arn", "N/A")

                    output.append(f"  ID: {resource_id}")
                    output.append(f"  ARN: {resource_arn}")

                    # Add details if present
                    details = resource.get("details", {})
                    if details:
                        output.append("  Details:")
                        for detail_key, value in sorted(details.items()):
                            output.append(f"    {detail_key}: {value}")

                    # Add tags if present
                    tags = resource.get("tags", [])
                    if tags:
                        output.append("  Tags:")
                        if isinstance(tags, list):
                            for tag in tags:
                                if isinstance(tag, dict):
                                    key = tag.get("Key", "N/A")
                                    value = tag.get("Value", "N/A")
                                    output.append(f"    {key}: {value}")
                        elif isinstance(tags, dict):
                            for tag_key, value in sorted(tags.items()):
                                output.append(f"    {tag_key}: {value}")
                    output.append("")  # Empty line for readability

        return "\n".join(output)

    except Exception as e:
        logger.exception("Error formatting output")
        return f"Error formatting output: {str(e)}"
