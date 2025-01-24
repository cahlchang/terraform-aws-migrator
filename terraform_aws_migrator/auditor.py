import time
from typing import Dict, List, Set, Any
import boto3
import traceback
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

    def __init__(self, exclusion_file: str = None, target_resource_type: str = None):
        self.session = boto3.Session()
        self.state_reader = TerraformStateReader(self.session)
        self.console = Console()
        self.start_time = None
        self.exclusion_config = ResourceExclusionConfig(exclusion_file)
        self.target_resource_type = target_resource_type
        self.resource_type_mappings = {}

    def get_terraform_managed_resources(self, tf_dir: str, progress=None) -> Set[str]:
        """Get set of resource identifiers managed by Terraform"""
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
            return set()

    def _get_relevant_collectors(self):
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

    def audit_resources(self, tf_dir: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect AWS resources that are not managed by Terraform, optionally filtered by type"""
        self.start_time = time.time()
        result: Dict[str, List[Dict[str, Any]]] = {"managed": {}, "unmanaged": {}}

        def get_elapsed_time() -> str:
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

            # Group managed resources by service
            for resource in managed_resources.values():
                service_name = (
                    resource.get("type", "").split("_")[1]
                    if resource.get("type", "").startswith("aws_")
                    else "other"
                )
                if service_name not in result["managed"]:
                    result["managed"][service_name] = []
                result["managed"][service_name].append(resource)

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

                    # Filter unmanaged resources
                    unmanaged = self._filter_unmanaged_resources(
                        resources, managed_resources
                    )

                    if unmanaged:
                        type_groups = {}
                        for resource in unmanaged:
                            resource_type = resource.get("type", "unknown")
                            if resource_type not in type_groups:
                                type_groups[resource_type] = []
                            type_groups[resource_type].append(resource)

                        for resource_type, resources_list in type_groups.items():
                            display_name = collector.get_type_display_name(
                                resource_type
                            )
                            self.console.print(
                                f"[green]Found {len(resources_list)} unmanaged {display_name} {get_elapsed_time()}"
                            )

                        # Add to result['unmanaged']
                        if service_name not in result["unmanaged"]:
                            result["unmanaged"][service_name] = []
                        result["unmanaged"][service_name].extend(unmanaged)

                except Exception as e:
                    self.console.print(
                        f"[red]Error collecting {service_name} resources: {str(e)}"
                    )

            # Complete the collection task
            progress.update(aws_task, completed=True)

        # Display total execution time
        total_time = int(time.time() - self.start_time)
        minutes = total_time // 60
        seconds = total_time % 60
        self.console.print(
            f"\n[green]Total execution time: [{minutes:02d}:{seconds:02d}]"
        )

        return result

    def _filter_unmanaged_resources(
        self, resources: List[Dict[str, Any]], managed_resources: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter out resources that are managed by Terraform or explicitly excluded"""
        unmanaged = []
        managed_identifiers = set()

        # Create a set of managed resource identifiers
        for resource in managed_resources.values():
            resource_type = resource.get("type")
            identifier = resource.get("arn") or resource.get("id")
            if identifier:
                managed_identifiers.add(identifier)
                # S3Policy (TODO: Refactor this)
                if resource_type == "aws_s3_bucket_policy":
                    bucket_name = identifier
                    bucket_arn = f"arn:aws:s3:::{bucket_name}"
                    managed_identifiers.add(bucket_name)
                    managed_identifiers.add(bucket_arn)
                    logger.debug(f"Added S3 bucket policy identifiers: {bucket_name}, {bucket_arn}")

        for resource in resources:
            resource_type = resource.get("type")
            identifier = resource.get("arn") or resource.get("id")
            
            # TODO: Refactor this
            if resource_type in ["aws_s3_bucket_policy", "aws_s3_bucket_acl"]:
                bucket_name = resource.get("id")
                bucket_arn = f"arn:aws:s3:::{bucket_name}"
                logger.info(f"Checking S3 {resource_type}: {bucket_name}")
                
                is_managed = False
                resource_id_in_state = False
                for state_resource in managed_resources.values():
                    state_type = state_resource.get("type")
                    state_id = state_resource.get("id")
                    
                    if state_type == resource_type and state_id == bucket_name:
                        logger.info(f"Found exact match for {resource_type}:{bucket_name} in state")
                        is_managed = True
                        break
                    
                    if state_type == resource_type:
                        from terraform_aws_migrator.generators.aws_storage.s3 import S3BucketACLGenerator
                        generator = S3BucketACLGenerator()
                        state_resource_name = generator._generate_resource_name(state_id)
                        current_resource_name = generator._generate_resource_name(bucket_name)
                        if state_resource_name == current_resource_name:
                            logger.info(f"Resource name collision detected for {bucket_name}")
                            resource_id_in_state = True
                            break
                
                if resource_id_in_state:
                    logger.info(f"Skipping {resource_type} for {bucket_name} due to resource name collision")
                    continue
                
                if not is_managed:
                    logger.info(f"Found unmanaged {resource_type}: {bucket_name}")
                    if not self.exclusion_config.should_exclude(resource):
                        if self.target_resource_type:
                            if self.target_resource_type.startswith("aws_"):
                                if resource_type == self.target_resource_type:
                                    logger.info(f"Adding unmanaged {resource_type}: {bucket_name}")
                                    unmanaged.append(resource)
                            else:
                                if resource_type and resource_type.startswith(f"aws_{self.target_resource_type}_"):
                                    logger.info(f"Adding unmanaged {resource_type}: {bucket_name}")
                                    unmanaged.append(resource)
                        else:
                            logger.info(f"Adding unmanaged {resource_type}: {bucket_name}")
                            unmanaged.append(resource)
                else:
                    logger.info(f"{resource_type} is managed: {bucket_name}")
            # common case
            elif identifier and identifier not in managed_identifiers:
                if not self.exclusion_config.should_exclude(resource):
                    if self.target_resource_type:
                        resource_type = resource.get("type")
                        if self.target_resource_type.startswith("aws_"):
                            # complete resource type is specified
                            if resource_type == self.target_resource_type:
                                unmanaged.append(resource)
                        else:
                            # category is specified
                            if resource_type and resource_type.startswith(f"aws_{self.target_resource_type}_"):
                                unmanaged.append(resource)
                    else:
                        unmanaged.append(resource)

        return unmanaged
