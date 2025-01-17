# terraform_aws_migrator/auditor.py

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

        service_name = None
        for collector in collectors:
            resource_types = collector.get_resource_types()
            if self.target_resource_type in resource_types:
                service_name = collector.get_service_name()
                logger.debug(f"Found service {service_name} for resource type {self.target_resource_type}")
                break

        if not service_name:
            logger.error(f"No collector found supporting resource type: {self.target_resource_type}")
            return []

        # return collectors for the specific service
        relevant_collectors = [
            collector
            for collector in collectors
            if collector.get_service_name() == service_name
        ]

        for collector in relevant_collectors:
            self.resource_type_mappings.update(collector.get_resource_types())
            logger.debug(
                f"Updated mappings from {collector.__class__.__name__}: {collector.get_resource_types()}"
            )

        return relevant_collectors

    def audit_specific_resource(
        self, tf_dir: str, target_resource_type: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect specific AWS resources that are not managed by Terraform"""
        self.start_time = time.time()
        self.target_resource_type = target_resource_type
        unmanaged_resources = {}

        def get_elapsed_time() -> str:
            elapsed = int(time.time() - self.start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            return f"[{minutes:02d}:{seconds:02d}]"

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}", style="bold blue"),
            CompactTimeColumn(),
            console=self.console,
            expand=False,
            refresh_per_second=10,
        ) as progress:
            # Get Terraform managed resources
            tf_task = progress.add_task("[cyan]Reading Terraform state...", total=None)
            managed_resources = self.get_terraform_managed_resources(tf_dir, progress)
            progress.update(tf_task, completed=True)

            # Get collectors and identify resource types
            collectors = self._get_relevant_collectors()
            if not collectors:
                return {}

            aws_task = progress.add_task(
                "[cyan]Collecting AWS resources...", total=None
            )

            # Process each collector
            for collector in collectors:
                self.target_resource_type
                try:
                    resources = collector.collect(target_resource_type=self.target_resource_type)
                    self.resource_type_mappings.update(collector.get_resource_types())
                    self.console.print(
                        f"Collector {self.target_resource_type} found {len(resources)} resources"
                    )

                    unmanaged_list = self._filter_unmanaged_resources(
                        resources, managed_resources
                    )
                    for unmanaged in unmanaged_list:
                        unmanaged_resources[unmanaged["id"]] = unmanaged

                    logger.debug(
                        f"After filtering: {len(unmanaged_resources)} unmanaged resources for {self.target_resource_type}"
                    )

                    for resource_type, resources in self._group_by_type(unmanaged_resources):
                        display_name = self.resource_type_mappings.get(
                            resource_type, resource_type
                        )
                        self.console.print(
                            f"[green]found {len(resources)} unmanaged {display_name} {get_elapsed_time()}"
                        )

                except Exception as e:
                    logger.error(f"Error collecting {self.target_resource_type} resources: {str(e)}")
                    self.console.print(f"[red]Error during detection: {traceback.format_exc()}")

            progress.update(aws_task, completed=True)

        return unmanaged_resources

    def _group_by_type(self, resources: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Group resources by their type"""
        grouped = {}
        for resource_id, resource in resources.items():
            if isinstance(resource, dict):
                resource_type = resource.get("type", "unknown")
                if resource_type not in grouped:
                    grouped[resource_type] = []
                grouped[resource_type].append(resource)
        return grouped.items()

    def audit_all_resources(self, tf_dir: str) -> Dict[str, List[Dict[str, Any]]]:
            """Detect AWS resources that are not managed by Terraform"""
            self.start_time = time.time()
            result = {
                'managed': {},
                'unmanaged': {}
            }
            
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
                tf_task = progress.add_task("[yellow]Reading Terraform state...", total=None)
                managed_resources = self.get_terraform_managed_resources(tf_dir, progress)
                progress.update(tf_task, completed=True)
                
                # Group managed resources by service
                for resource in managed_resources.values():
                    service_name = resource.get('type', '').split('_')[1] if resource.get('type', '').startswith('aws_') else 'other'
                    if service_name not in result['managed']:
                        result['managed'][service_name] = []
                    result['managed'][service_name].append(resource)

                self.console.print(
                    f"Found {len(managed_resources)} managed resources in Terraform state {get_elapsed_time()}"
                )

                # Initialize collectors
                collectors = [collector_cls(self.session) for collector_cls in registry]

                # Add main AWS resource collection task
                aws_task = progress.add_task(
                    "[cyan]Collecting AWS resources...", total=None
                )

                # Process each collector
                for collector in collectors:
                    service_name = collector.get_service_name()
                    try:
                        # Update progress description
                        resource_types = collector.get_resource_types()
                        resource_type_names = ", ".join(resource_types.values())
                        progress.update(
                            aws_task,
                            description=f"[cyan]Collecting {resource_type_names}...",
                        )

                        # Collect resources
                        resources = collector.collect()
                        
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
                            if service_name not in result['unmanaged']:
                                result['unmanaged'][service_name] = []
                            result['unmanaged'][service_name].extend(unmanaged)

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

    def _filter_unmanaged_resources(self, resources: List[Dict[str, Any]], managed_resources: Dict[str, Any]) -> List[Dict[str, Any]]:
            """Filter out resources that are managed by Terraform or explicitly excluded"""
            unmanaged = []
            managed_identifiers = set()

            # Create a set of managed resource identifiers
            for resource in managed_resources.values():
                identifier = resource.get('arn') or resource.get('id')
                if identifier:
                    managed_identifiers.add(identifier)

            for resource in resources:
                identifier = resource.get('arn') or resource.get('id')
                if identifier and identifier not in managed_identifiers:
                    if not self.exclusion_config.should_exclude(resource):
                        if self.target_resource_type:
                            if resource.get("type") == self.target_resource_type:
                                unmanaged.append(resource)
                        else:
                            unmanaged.append(resource)

            return unmanaged
