import time
from typing import Dict, List, Set, Any, Optional, Union
import boto3
import traceback
import copy
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    ProgressColumn,
    Task,
)
from rich.text import Text

from terraform_aws_migrator.collectors.base import registry
from terraform_aws_migrator.state_reader import TerraformStateReader
from terraform_aws_migrator.exclusion import ResourceExclusionConfig

import logging

logger = logging.getLogger(__name__)


class CompactTimeColumn(ProgressColumn):
    """Custom time column that displays elapsed time in a compact format"""

    def __init__(self):
        super().__init__()
        self.start_time = time.time()

    def render(self, task: "Task") -> Text:
        """Render the time column."""
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return Text(f"[{minutes:02d}:{seconds:02d}]")


class AWSResourceAuditor:
    """Main class for detecting unmanaged AWS resources"""

    def __init__(
        self,
        exclusion_file: Optional[str] = None,
        target_resource_type: Optional[str] = None,
    ):
        self.session = boto3.Session()
        self.state_reader = TerraformStateReader(self.session)
        self.console = Console()
        self.start_time: Optional[float] = None
        self.exclusion_config = ResourceExclusionConfig(exclusion_file)
        self.target_resource_type = target_resource_type
        self.resource_type_mappings: Dict[str, str] = {}

    def get_terraform_managed_resources(
        self, tf_dir: str, progress=None
    ) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of resource identifiers managed by Terraform"""
        try:
            managed_resources = self.state_reader.get_managed_resources(
                tf_dir, progress
            )
            self.console.print(
                f"[cyan]Found {len(managed_resources)} managed resources in Terraform state"
            )
            return managed_resources
        except Exception as e:
            self.console.print(f"[red]Error reading Terraform state: {str(e)}")
            return {}

    def _get_relevant_collectors(self) -> List[Any]:
        """Get collectors based on target_resource_type"""
        collectors = registry.get_collectors(self.session)

        if not self.target_resource_type:
            logger.debug(f"Getting all collectors: {len(collectors)}")
            return collectors

        matching_collectors = []
        for collector in collectors:
            resource_types = collector.get_resource_types()
            service_name = collector.get_service_name()

            # apply category filter
            if not self.target_resource_type.startswith("aws_"):
                if self.target_resource_type == service_name:
                    matching_collectors.append(collector)
            # apply resource type filter
            elif self.target_resource_type in resource_types:
                matching_collectors.append(collector)

        if not matching_collectors:
            logger.error(
                f"No collector found supporting resource type or service: {self.target_resource_type}"
            )
            return []

        # Add resource type mappings from all matching collectors
        for collector in matching_collectors:
            self.resource_type_mappings.update(collector.get_resource_types())

        return matching_collectors

    def audit_resources(
        self, tf_dir: str
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Detect AWS resources that are not managed by Terraform, optionally filtered by type"""
        self.start_time = time.time()
        result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"all_resources": {}}
        managed_resources = {}

        def get_elapsed_time() -> str:
            if self.start_time is None:
                return "[00:00]"
            elapsed = int(time.time() - self.start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            return f"[{minutes:02d}:{seconds:02d}]"

        progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}", style="bold blue"),
            CompactTimeColumn(),
            console=self.console,
            expand=False,
            refresh_per_second=10,
        )

        with progress:
            # Get Terraform managed resources
            tf_task = progress.add_task(
                "[yellow]Reading Terraform state...", total=None
            )
            managed_resources = self.get_terraform_managed_resources(tf_dir, progress)
            progress.update(tf_task, completed=True)

            # Group managed resources by service and collect details
            collectors = self._get_relevant_collectors()
            for resource in managed_resources.values():
                service_name = (
                    resource.get("type", "").split("_")[1]
                    if resource.get("type", "").startswith("aws_")
                    else "other"
                )

                # Collect details for managed resources
                for collector in collectors:
                    if collector.get_service_name() == service_name:
                        try:
                            collected = collector.collect(
                                target_resource_type=resource.get("type")
                            )
                            for c in collected:
                                if c.get("id") == resource.get("id"):
                                    resource["details"] = c.get("details", {})
                                    break
                        except Exception as e:
                            logger.error(
                                f"Error collecting details for managed resource {resource.get('id')}: {str(e)}"
                            )

                # Add managed flag
                resource["managed"] = True

                if service_name not in result["all_resources"]:
                    result["all_resources"][service_name] = []
                result["all_resources"][service_name].append(resource)

            # Initialize collectors
            collectors = self._get_relevant_collectors()
            if not collectors:
                if self.target_resource_type:
                    self.console.print(
                        f"[red]No collectors found for resource type: {self.target_resource_type}"
                    )
                return result

            # Add main AWS resource collection task
            aws_task = progress.add_task(
                "[cyan]Collecting AWS resources...", total=None
            )

            # Process each collector
            for collector in collectors:
                service_name = collector.get_service_name()
                try:
                    # Update progress description
                    progress.update(
                        aws_task,
                        description=f"[cyan]Collecting {service_name} resources...",
                    )

                    # Collect resources, passing target_resource_type if specified
                    resources = collector.collect(
                        target_resource_type=self.target_resource_type
                    )

                    # Create managed resources lookup
                    managed_lookup = {
                        (resource.get("type"), resource.get("id")): resource
                        for resource in managed_resources.values()
                    }

                    # Process collected resources
                    processed_resources = []
                    for resource in resources:
                        # Skip excluded resources
                        if self.exclusion_config.should_exclude(resource):
                            continue

                        resource_type = resource.get("type")
                        if not resource_type or not self._matches_target_type(
                            resource_type
                        ):
                            continue

                        # Check if resource is managed
                        resource_id = resource.get("id")
                        managed_resource = managed_lookup.get(
                            (resource_type, resource_id)
                        )

                        if managed_resource:
                            # Use managed resource but keep details from collector
                            managed_copy = copy.deepcopy(managed_resource)
                            managed_copy["details"] = resource.get("details", {})
                            managed_copy["managed"] = True
                            processed_resources.append(managed_copy)
                        else:
                            # Use collected resource
                            resource_copy = copy.deepcopy(resource)
                            resource_copy["managed"] = False
                            processed_resources.append(resource_copy)

                    if processed_resources:
                        type_groups: Dict[str, List[Dict[str, Any]]] = {}
                        for resource in processed_resources:
                            resource_type = resource.get("type", "unknown")
                            if resource_type not in type_groups:
                                type_groups[resource_type] = []
                            type_groups[resource_type].append(resource)

                        for resource_type, resources_list in type_groups.items():
                            display_name = collector.get_type_display_name(
                                resource_type
                            )
                            managed_count = sum(
                                1 for r in resources_list if r.get("managed", False)
                            )
                            unmanaged_count = len(resources_list) - managed_count
                            self.console.print(
                                f"[green]Found {len(resources_list)} {display_name} ({managed_count} managed, {unmanaged_count} unmanaged) {get_elapsed_time()}"
                            )

                        # Add to result['all_resources']
                        if service_name not in result["all_resources"]:
                            result["all_resources"][service_name] = []
                        result["all_resources"][service_name].extend(
                            processed_resources
                        )

                except Exception as e:
                    self.console.print(
                        f"[red]Error collecting {service_name} resources: {str(e)}"
                    )

            # Complete the collection task
            progress.update(aws_task, completed=True)

        # Display total execution time
        if self.start_time is not None:
            total_time = int(time.time() - self.start_time)
            minutes = total_time // 60
            seconds = total_time % 60
            self.console.print(
                f"\n[green]Total execution time: [{minutes:02d}:{seconds:02d}]"
            )

        return result

    def _matches_target_type(self, resource_type: Optional[str]) -> bool:
        """Check if resource type matches target type filter"""
        if not self.target_resource_type:
            return True

        if not resource_type:
            return False

        if self.target_resource_type.startswith("aws_"):
            return resource_type == self.target_resource_type

        return resource_type.startswith(f"aws_{self.target_resource_type}_")

    def _process_s3_resource(
        self, resource: Dict[str, Any], managed_resources: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process S3 bucket policy and ACL resources"""
        resource_type = resource.get("type")
        bucket_name = resource.get("id")

        # Check for exact match in managed resources
        for state_resource in managed_resources.values():
            if (
                state_resource.get("type") == resource_type
                and state_resource.get("id") == bucket_name
            ):
                return None

            # Check for resource name collision
            if state_resource.get("type") == resource_type:
                from terraform_aws_migrator.generators.aws_storage.s3 import (
                    S3BucketACLGenerator,
                )

                generator = S3BucketACLGenerator()
                state_id = state_resource.get("id")
                if (
                    state_id
                    and bucket_name
                    and (
                        generator._generate_resource_name(state_id)
                        == generator._generate_resource_name(bucket_name)
                    )
                ):
                    return None

        # If not managed and matches target type, return copy of resource
        if resource_type and self._matches_target_type(resource_type):
            copied_resource = copy.deepcopy(resource)
            if not copied_resource.get("details") and resource.get("details"):
                copied_resource["details"] = copy.deepcopy(resource["details"])
            return copied_resource
        return None

    def _process_s3_resource(
        self, resource: Dict[str, Any], managed_resources: Dict[str, Any]
    ) -> bool:
        """Check if S3 resource is managed"""
        resource_type = resource.get("type")
        if resource_type not in ["aws_s3_bucket_policy", "aws_s3_bucket_acl"]:
            return False

        for state_resource in managed_resources.values():
            if state_resource.get("type") == resource_type and state_resource.get(
                "id"
            ) == resource.get("id"):
                return True
        return False
