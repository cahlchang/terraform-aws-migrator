import time
from typing import Dict, List, Any, Optional
import boto3
import traceback
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import logging

from terraform_aws_migrator.collectors.base import registry
from terraform_aws_migrator.state_reader import TerraformStateReader
from terraform_aws_migrator.exclusion import ResourceExclusionConfig
from terraform_aws_migrator.resource_management import ResourceManagementChecker
from terraform_aws_migrator.progress_tracking import CompactTimeColumn, TimeTracker
from terraform_aws_migrator.resource_processor import ResourceProcessor

logger = logging.getLogger(__name__)

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
        self.time_tracker = TimeTracker()
        self.exclusion_config = ResourceExclusionConfig(exclusion_file)
        self.target_resource_type = target_resource_type
        self.resource_type_mappings: Dict[str, str] = {}
        self.resource_management = ResourceManagementChecker()
        self.resource_processor = ResourceProcessor(self.console)

    def get_terraform_managed_resources(
        self, tf_dir: str, progress=None
    ) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of resource identifiers managed by Terraform"""
        try:
            managed_resources = self.state_reader.get_managed_resources(tf_dir, progress)
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
        self.time_tracker.start()
        result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"all_resources": {}}
        managed_resources = {}

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

            # Initialize collectors once
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

                    # Collect resources
                    resources = collector.collect(
                        target_resource_type=self.target_resource_type
                    )

                    # Create managed resources lookup
                    managed_lookup = self.resource_management.create_managed_lookup(
                        managed_resources, collector
                    )

                    # Process collected resources
                    processed_resources = []
                    for resource in resources:
                        resource_type = resource.get("type")
                        if not resource_type or not self.resource_processor.matches_target_type(
                            resource_type, self.target_resource_type
                        ):
                            continue

                        # Skip excluded resources
                        if self.exclusion_config.should_exclude(resource):
                            logger.debug(f"Excluding resource: {resource}")
                            continue

                        processed_resource = self.resource_management.process_resource(
                            resource, managed_lookup, collector
                        )
                        if processed_resource:
                            processed_resources.append(processed_resource)

                    if processed_resources:
                        # Group resources by type and display summary
                        type_groups = self.resource_processor.group_resources_by_type(
                            processed_resources,
                            collector,
                            self.time_tracker.get_elapsed_time
                        )

                        # Add to result['all_resources']
                        if service_name not in result["all_resources"]:
                            result["all_resources"][service_name] = []
                        result["all_resources"][service_name].extend(processed_resources)

                except Exception as e:
                    self.console.print(
                        f"[red]Error collecting {service_name} resources: {str(e)}"
                    )

            # Complete the collection task
            progress.update(aws_task, completed=True)

        # Display total execution time
        total_time = self.time_tracker.get_total_time()
        if total_time:
            self.console.print(f"\n[green]Total execution time: {total_time}")

        return result
