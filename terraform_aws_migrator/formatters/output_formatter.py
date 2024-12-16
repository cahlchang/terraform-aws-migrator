# terraform_aws_detector/formatters/output_formatter.py

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Union
from collections import defaultdict
from terraform_aws_migrator.utils.resource_utils import get_collectors_info

logger = logging.getLogger(__name__)

def get_resource_to_category_mapping():
    """Create a mapping of resource types to their categories using collector info"""
    categories = get_collectors_info()
    mapping = {}
    for category, resources in categories.items():
        for resource in resources:
            mapping[resource['type']] = category
    return mapping

def datetime_handler(obj):
    """Handler for datetime objects during JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

def format_value(value: Any) -> str:
    """Format any value to a string, handling special types like datetime"""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

def format_output(
    resources: Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]],
    output_format: str = "text",
) -> str:
    """
    Format the unmanaged resources according to the specified output format.

    Args:
        resources: List of resources or Dict of service names to resource lists
        output_format: Output format ('text' or 'json')

    Returns:
        Formatted string representation of the resources
    """
    try:
        logger.debug(f"Resources received: {resources}")

        if output_format == "json":
            return json.dumps(resources, indent=2, default=datetime_handler)

        # Default text format
        if not resources:
            return "No unmanaged resources found."

        output = []
        output.append("Unmanaged AWS Resources:")
        output.append("-" * 40)

        # Get resource type to category mapping
        resource_categories = get_resource_to_category_mapping()

        # Group resources by category and type
        categorized_resources = defaultdict(lambda: defaultdict(list))

        if isinstance(resources, dict):
            for service_name, service_resources in resources.items():
                for resource in service_resources:
                    if not isinstance(resource, dict):
                        continue
                    resource_type = str(resource.get("type", "unknown"))
                    category = resource_categories.get(resource_type, "Other")
                    categorized_resources[category][resource_type].append(resource)
        else:
            for resource in resources:
                if not isinstance(resource, dict):
                    continue
                resource_type = str(resource.get("type", "unknown"))
                category = resource_categories.get(resource_type, "Other")
                categorized_resources[category][resource_type].append(resource)

        # Output resources by category and type
        for category in sorted(categorized_resources.keys()):
            output.append(f"\n{category}")
            for resource_type, resources_list in sorted(categorized_resources[category].items()):
                output.append(f"\n{resource_type}:")
                
                # Sort resources by ID for consistent output
                sorted_resources = sorted(resources_list, key=lambda x: str(x.get('id', '')))
                
                for resource in sorted_resources:
                    output.append(f"  - ID: {format_value(resource.get('id', 'N/A'))}")
                    if resource.get('arn'):
                        output.append(f"    ARN: {format_value(resource.get('arn'))}")

                    # Handle details if present
                    details = resource.get("details", {})
                    if details and isinstance(details, dict):
                        output.append("    Details:")
                        for key, value in sorted(details.items()):
                            output.append(f"      {key}: {format_value(value)}")

                    # Handle tags
                    tags = resource.get("tags", [])
                    if tags:
                        output.append("    Tags:")
                        if isinstance(tags, list):
                            for tag in sorted(tags, key=lambda x: str(x.get('Key', ''))):
                                if isinstance(tag, dict):
                                    output.append(
                                        f"      {tag.get('Key', 'N/A')}: {format_value(tag.get('Value', 'N/A'))}"
                                    )
                        elif isinstance(tags, dict):
                            for key in sorted(tags.keys()):
                                output.append(f"      {key}: {format_value(tags[key])}")
                    output.append("")

        return "\n".join(output)

    except Exception as e:
        logger.exception("Error formatting output")
        return f"Error formatting output: {str(e)}"
