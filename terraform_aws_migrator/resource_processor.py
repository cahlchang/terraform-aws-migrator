from typing import Dict, List, Any, Optional
import logging
from rich.console import Console

logger = logging.getLogger(__name__)

class ResourceProcessor:
    """Class responsible for processing and grouping AWS resources"""

    def __init__(self, console: Console):
        self.console = console

    def group_resources_by_type(
        self,
        resources: List[Dict[str, Any]],
        collector: Any,
        elapsed_time_fn: callable
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group resources by type and display summary"""
        if not resources:
            return {}

        type_groups: Dict[str, List[Dict[str, Any]]] = {}
        
        # Group resources by type
        for resource in resources:
            resource_type = resource.get("type", "unknown")
            if resource_type not in type_groups:
                type_groups[resource_type] = []
            type_groups[resource_type].append(resource)

        # Display summary for each type
        for resource_type, resources_list in type_groups.items():
            display_name = collector.get_type_display_name(resource_type)
            managed_count = sum(1 for r in resources_list if r.get("managed", False))
            unmanaged_count = len(resources_list) - managed_count
            
            if unmanaged_count > 0:
                self.console.print(
                    f"[green]Found {unmanaged_count} unmanaged {display_name} {elapsed_time_fn()}"
                )

        return type_groups

    def process_s3_resource(
        self,
        resource: Dict[str, Any],
        managed_resources: Dict[str, Any]
    ) -> bool:
        """Check if S3 resource is managed"""
        resource_type = resource.get("type")
        if resource_type not in ["aws_s3_bucket_policy", "aws_s3_bucket_acl"]:
            return False

        for state_resource in managed_resources.values():
            if (state_resource.get("type") == resource_type and 
                state_resource.get("id") == resource.get("id")):
                return True
        return False

    def matches_target_type(
        self,
        resource_type: Optional[str],
        target_resource_type: Optional[str]
    ) -> bool:
        """Check if resource type matches target type filter"""
        if not target_resource_type:
            return True

        if not resource_type:
            return False

        # If target is a full AWS resource type (e.g., aws_instance)
        if target_resource_type.startswith("aws_"):
            return resource_type == target_resource_type

        # If target is a service name (e.g., ec2, network)
        if resource_type.startswith("aws_"):
            # Extract full service name from resource type (e.g., aws_instance -> instance, aws_vpc -> vpc)
            resource_service = resource_type[4:]  # Remove 'aws_' prefix
            
            # Map common service names
            service_mappings = {
                "instance": "ec2",
                "vpc": "network",
                "subnet": "network",
                "route": "network",
                "security_group": "ec2"
            }
            
            # First try to map the full service name
            if resource_service in service_mappings:
                resource_service = service_mappings[resource_service]
            else:
                # If full name doesn't match, try the first part
                resource_service = resource_service.split("_")[0]
                resource_service = service_mappings.get(resource_service, resource_service)
            return resource_service == target_resource_type

        return False
