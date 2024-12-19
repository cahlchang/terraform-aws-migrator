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

        service_name = self.target_resource_type.split('_')[1]
        logger.debug(f"Looking for collectors for service: {service_name}")
        
        # First collect all resource types from relevant collectors
        for collector in collectors:
            logger.debug(f"Checking collector: {collector.__class__.__name__}")
            if collector.get_service_name() == service_name:
                self.resource_type_mappings.update(collector.get_resource_types())
                logger.debug(f"Updated mappings from {collector.__class__.__name__}: {collector.get_resource_types()}")
        
        relevant_collectors = [
            collector for collector in collectors
            if collector.get_service_name() == service_name
        ]
        logger.debug(f"Found relevant collectors: {[c.__class__.__name__ for c in relevant_collectors]}")
        
        return relevant_collectors

    def audit_specific_resource(self, tf_dir: str, target_resource_type: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect specific AWS resources that are not managed by Terraform"""
        self.target_resource_type = target_resource_type
        logger.debug(f"Starting audit for resource type: {target_resource_type}")
        
        self.start_time = time.time()
        unmanaged_resources = {}
        resource_counts = {}

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
            tf_task = progress.add_task("[cyan]Reading Terraform state...", total=None)
            managed_resources = self.get_terraform_managed_resources(tf_dir, progress)
            progress.update(tf_task, completed=True)
            self.console.print(
                f"[green]Found {len(managed_resources)} managed resources in Terraform state {get_elapsed_time()}"
            )

            # Get collectors first to populate resource_type_mappings
            collectors = self._get_relevant_collectors()
            
            # Get related resource types
            base_resource = self.target_resource_type.split('_')[-1]
            related_types = [
                rtype for rtype in self.resource_type_mappings.keys()
                if f"_{base_resource}" in rtype or
                   f"{base_resource}_policy" in rtype or
                   f"{base_resource}_policy_attachment" in rtype
            ]
            
            # Display what we're collecting
            self.console.print(f"[cyan]Collecting {', '.join(related_types)}...")

            aws_task = progress.add_task("[cyan]Collecting AWS resources...", total=None)

            # Process each collector
            for collector in collectors:
                service_name = collector.get_service_name()
                logger.debug(f"Processing collector for service: {service_name}")
                try:
                    resources = collector.collect()
                    logger.debug(f"Collected {len(resources)} resources from {service_name}")
                    
                    for resource in resources:
                        logger.debug(f"Resource found: {resource.get('type')} - {resource.get('id')}")

                    unmanaged = self._filter_unmanaged_resources(resources, managed_resources)
                    logger.debug(f"Found {len(unmanaged)} unmanaged resources for {service_name}")

                    if unmanaged:
                        if service_name not in unmanaged_resources:
                            unmanaged_resources[service_name] = []
                        unmanaged_resources[service_name].extend(unmanaged)

                        # Group by resource type for summary
                        for resource in unmanaged:
                            resource_type = resource.get("type", "unknown")
                            if resource_type not in resource_counts:
                                resource_counts[resource_type] = []
                            resource_counts[resource_type].append(resource)

                except Exception as e:
                    logger.error(f"Error collecting {service_name} resources: {str(e)}")
                    self.console.print(f"[red]Error collecting {service_name} resources: {str(e)}")

            # Display summary for each related resource type
            for resource_type, resources in resource_counts.items():
                display_name = self.resource_type_mappings.get(resource_type, resource_type)
                for resource in resources:
                    self.console.print(
                        f"[green]Found unmanaged {display_name}: {resource.get('id')} {get_elapsed_time()}"
                    )

            progress.update(aws_task, completed=True)

        total_time = int(time.time() - self.start_time)
        minutes = total_time // 60
        seconds = total_time % 60
        self.console.print(f"\n[green]Total execution time: [{minutes:02d}:{seconds:02d}]")
        
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
