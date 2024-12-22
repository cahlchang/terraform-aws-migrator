# terraform_aws_migrator/formatters/output_formatter.py

import json
from typing import Dict, List, Any
import logging
from ..collectors.base import registry

logger = logging.getLogger(__name__)


def format_output(
    resources: Dict[str, Dict[str, List[Dict[str, Any]]]], output_format: str = "text"
) -> str:
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
        managed_resources = resources.get("managed", {})
        unmanaged_resources = resources.get("unmanaged", {})

        # Count total resources
        total_managed = sum(len(res_list) for res_list in managed_resources.values())
        total_unmanaged = sum(
            len(res_list) for res_list in unmanaged_resources.values()
        )
        total_resources = total_managed + total_unmanaged

        # Resource Summary
        output.append("\nResource Summary:")
        output.append(f"Total Resources: {total_resources}")
        output.append(f"Managed by Terraform: {total_managed}")
        output.append(f"Not Managed by Terraform: {total_unmanaged}")
        output.append(
            f"Management Ratio: {(total_managed / total_resources * 100):.1f}% managed"
        )

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

        # Calculate total resources by type (combining managed and unmanaged)
        total_by_type = {}

        # Count managed resources by type
        for service_name, resources in managed_resources.items():
            for resource in resources:
                resource_type = resource.get("type", "unknown")
                full_type = f"{service_name}.{resource_type}"
                if full_type not in total_by_type:
                    total_by_type[full_type] = {"total": 0, "unmanaged": 0}
                total_by_type[full_type]["total"] += 1

        # Add unmanaged counts and update totals
        for full_type, resources_list in resource_counts.items():
            if full_type not in total_by_type:
                total_by_type[full_type] = {
                    "total": len(resources_list),
                    "unmanaged": len(resources_list),
                }
            else:
                total_by_type[full_type]["unmanaged"] = len(resources_list)
                total_by_type[full_type]["total"] += len(resources_list)

        # Resources Summary by Type
        if total_by_type:
            output.append("\nResources by Type:")
            for full_type, counts in sorted(total_by_type.items()):
                if counts["unmanaged"] > 0:  # Only show types with unmanaged resources
                    service_name, resource_type = full_type.split(".", 1)
                    collector_cls = collectors.get(service_name)

                    if collector_cls:
                        display_name = collector_cls.get_type_display_name(
                            resource_type
                        )
                    else:
                        display_name = full_type

                    output.append(
                        f"- Found {counts['unmanaged']} / {counts['total']} (unmanaged / all) {display_name}"
                    )

        # Detailed Resources Section
        if output_format == "text":
            output.append("\nDetailed Resources:")

            # Add managed resources details
            if managed_resources:
                output.append("\nManaged Resources:")
                for service_name, resources_list in sorted(managed_resources.items()):
                    collector_cls = collectors.get(service_name)
                    if not resources_list:
                        continue

                    output.append(f"\n{service_name.upper()} Service Resources:")
                    for resource in resources_list:
                        resource_type = resource.get("type", "unknown")
                        if collector_cls:
                            display_name = collector_cls.get_type_display_name(
                                resource_type
                            )
                        else:
                            display_name = resource_type

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
