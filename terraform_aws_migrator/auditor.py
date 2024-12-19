# terraform_aws_migrator/auditor.py

import time
from typing import Dict, List, Set, Any
import boto3
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
        if not self.target_resource_type:
            # If no specific type is targeted, return all collectors
            return [collector_cls(self.session) for collector_cls in registry]

        relevant_collectors = []
        for collector_cls in registry:
            # Check if this collector handles the target resource type
            resource_types = collector_cls.get_resource_types()
            if self.target_resource_type in resource_types:
                relevant_collectors.append(collector_cls(self.session))
                break  # We found the collector we need

        return relevant_collectors

    def audit_specific_resource(self, tf_dir: str, target_resource_type: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect AWS resources that are not managed by Terraform"""
        self.target_resource_type = target_resource_type
        self.start_time = time.time()
        unmanaged_resources = {}

        def get_elapsed_time() -> str:
            """Get elapsed time in [MM:SS] format"""
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
            self.console.print(
                f"[green]Found {len(managed_resources)} managed resources in Terraform state {get_elapsed_time()}"
            )

            # Get relevant collectors based on target_resource_type
            collectors = self._get_relevant_collectors()

            if self.target_resource_type:
                self.console.print(
                    f"[cyan]Collecting only {self.target_resource_type} resources..."
                )

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
                    if self.target_resource_type:
                        resource_type_names = resource_types[self.target_resource_type]
                    else:
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
                        if service_name not in unmanaged_resources:
                            unmanaged_resources[service_name] = []
                        unmanaged_resources[service_name].extend(unmanaged)

                        # Only show count for relevant resource types
                        for resource in unmanaged:
                            resource_type = resource.get("type", "unknown")
                            if (
                                not self.target_resource_type
                                or resource_type == self.target_resource_type
                            ):
                                display_name = collector.get_type_display_name(
                                    resource_type
                                )
                                self.console.print(
                                    f"[green]Found unmanaged {display_name}: {resource.get('id')} {get_elapsed_time()}"
                                )

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
        return unmanaged_resources

    def audit_all_resources(self, tf_dir: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect AWS resources that are not managed by Terraform"""
        self.start_time = time.time()
        unmanaged_resources = {}

        def get_elapsed_time() -> str:
            """Get elapsed time in [MM:SS] format"""
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

                        # unmanaged_resourcesに追加
                        if service_name not in unmanaged_resources:
                            unmanaged_resources[service_name] = []
                        unmanaged_resources[service_name].extend(unmanaged)

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

        return unmanaged_resources

    def _filter_unmanaged_resources(
        self, resources: List[Dict[str, Any]], managed_resources: Set[str]
    ) -> List[Dict[str, Any]]:
        """Filter out resources that are managed by Terraform or explicitly excluded"""
        unmanaged = []
        for resource in resources:
            identifiers = self._get_resource_identifiers(resource)
            if not any(identifier in managed_resources for identifier in identifiers):
                # Check if resource should be excluded
                if not self.exclusion_config.should_exclude(resource):
                    # If target_resource_type is specified, only include matching resources
                    if self.target_resource_type:
                        if resource.get("type") == self.target_resource_type:
                            unmanaged.append(resource)
                    else:
                        unmanaged.append(resource)
        return unmanaged

    def _get_resource_identifiers(self, resource: Dict[str, Any]) -> Set[str]:
        """Get all possible identifiers for a resource"""
        identifiers = set()

        # Add ARN if available
        if "arn" in resource:
            identifiers.add(resource["arn"])

        # Add ID if available
        if "id" in resource:
            identifiers.add(resource["id"])
            # Also add type:id format
            if "type" in resource:
                identifiers.add(f"{resource['type']}:{resource['id']}")

        return identifiers
