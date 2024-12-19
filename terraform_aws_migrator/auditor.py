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

    def __init__(self):
        self.session = boto3.Session()
        self.state_reader = TerraformStateReader(self.session)
        self.console = Console()
        self.start_time = None

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

    def audit_resources(self, tf_dir: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect AWS resources that are not managed by Terraform"""
        self.start_time = time.time()
        unmanaged_resources = {}

        # Create custom format for task description that includes elapsed time
        def format_task(task):
            return Text.assemble(
                (task.description, "bold blue"),
                " ",  # Space between description and time
            )

        # Create progress display with custom formatting
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
                    progress.update(
                        aws_task,
                        description=f"[cyan]Collecting {service_name} resources...",
                    )

                    # Collect resources
                    resources = collector.collect()

                    # Filter unmanaged resources
                    unmanaged = self._filter_unmanaged_resources(
                        resources, managed_resources
                    )
                    if unmanaged:
                        unmanaged_resources[service_name] = unmanaged
                        self.console.print(
                            f"[green]Found {len(unmanaged)} unmanaged {service_name} resources"
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

    def _filter_unmanaged_resources(
        self, resources: List[Dict[str, Any]], managed_resources: Set[str]
    ) -> List[Dict[str, Any]]:
        """Filter out resources that are managed by Terraform"""
        unmanaged = []
        for resource in resources:
            identifiers = self._get_resource_identifiers(resource)
            if not any(identifier in managed_resources for identifier in identifiers):
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
