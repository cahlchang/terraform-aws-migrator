# terraform_aws_detector/auditor.py

import json
import time
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import boto3
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel

from terraform_aws_detector.collectors.base import registry
from terraform_aws_detector.collection_status import CollectionStatus
from terraform_aws_detector.state_reader import TerraformStateReader


class AWSResourceAuditor:
    """Main class for detecting unmanaged AWS resources"""

    def __init__(self):
        self.session = boto3.Session()
        self.state_reader = TerraformStateReader(self.session)
        self.console = Console()
        self.collection_progress = CollectionStatus()
        self.start_time = None

    def get_elapsed_time(self) -> float:
        """Get elapsed time since audit started"""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def get_terraform_managed_resources(self, tf_dir: str, progress=None) -> Set[str]:
        """Get set of resource identifiers managed by Terraform"""
        try:
            managed_resources = self.state_reader.get_managed_resources(
                tf_dir, progress
            )
            self.console.print(
                f"[green]Found {len(managed_resources)} managed resources in Terraform state"
            )
            return managed_resources
        except Exception as e:
            self.console.print(f"[red]Error reading Terraform state: {str(e)}")
            return set()

    def audit_resources(self, tf_dir: str) -> Dict[str, List[Dict[str, Any]]]:
        """Detect AWS resources that are not managed by Terraform"""
        self.start_time = time.time()

        # Create console for progress display
        console = Console()

        # Set up progress tracking
        progress_columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
        ]

        with Progress(*progress_columns, console=console, transient=True) as progress:
            # Get Terraform managed resources
            tf_task = progress.add_task(
                "[yellow]Detecting Terraform managed resources...", total=None
            )

            tf_resources = self.get_terraform_managed_resources(tf_dir, progress)
            progress.update(tf_task, description="[green]Terraform resources detected")

            # Collect current AWS resources
            aws_task = progress.add_task("[cyan]Detecting AWS resources...", total=None)

            def progress_callback(
                service_name: str, status: str, resource_count: Optional[int] = None
            ):
                """Update progress during AWS resource collection"""
                # Update collection_progress
                self.collection_progress.update_service(
                    service_name, status, resource_count
                )
                current_time = int(self.get_elapsed_time())

                # Update task status
                self.collection_progress.update_task(
                    f"Processing: {service_name}", time=self.get_elapsed_time()
                )
                progress.update(
                    aws_task, description=f"[cyan]Processing: {service_name}"
                )

                # Only print completion messages
                if status == "Completed":
                    mins, secs = divmod(current_time, 60)
                    time_str = f"{mins:02d}:{secs:02d}"
                    console.print(
                        f"Completed: {service_name:<30} [{time_str}]", style="green"
                    )
                # Print info messages (like EBS volume exclusions)
                elif status.startswith("Info:"):
                    console.print(status, style="cyan")

            # Collect AWS resources
            aws_resources = registry.collect_all(progress_callback=progress_callback)
            console.print("[green]AWS resources detection completed")

            # Identify unmanaged resources
            analysis_task = progress.add_task(
                "[cyan]Identifying unmanaged resources...", total=None
            )
            unmanaged_resources = {}

            for service_name, resources in aws_resources.items():
                progress.update(
                    analysis_task,
                    description=f"[cyan]Analyzing {service_name} resources...",
                )
                unmanaged = []

                for resource in resources:
                    # Get resource identifiers
                    identifiers = self._get_resource_identifiers(resource)

                    # Check if any identifier is in tf_resources
                    if not any(
                        identifier in tf_resources for identifier in identifiers
                    ):
                        unmanaged.append(resource)

                if unmanaged:
                    unmanaged_resources[service_name] = unmanaged

                # Update progress
                self.collection_progress.update_service(
                    service_name, "Analyzed", len(unmanaged) if unmanaged else 0
                )

                current_time = int(self.get_elapsed_time())
                mins, secs = divmod(current_time, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                console.print(
                    f"Analyzed: {service_name:<30} [{time_str}]", style="yellow"
                )

            progress.update(analysis_task, description="[green]Analysis completed")
            console.print("[green]Analysis completed")

        return unmanaged_resources

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

        # Add any additional identifiers specific to the resource type
        additional_identifiers = self._get_additional_identifiers(resource)
        identifiers.update(additional_identifiers)

        return identifiers

    def _get_additional_identifiers(self, resource: Dict[str, Any]) -> Set[str]:
        """Get additional identifiers specific to resource type"""
        identifiers = set()

        # Add resource-type specific identifiers
        if resource.get("type") == "aws_s3_bucket":
            if "name" in resource:
                identifiers.add(f"arn:aws:s3:::{resource['name']}")

        # Add more resource type specific cases as needed

        return identifiers

    def _process_state_file(
        self, state_file: Path, managed_resources: Set[str]
    ) -> None:
        """Process a local Terraform state file and extract ARNs"""
        try:
            with open(state_file) as f:
                state_data = json.load(f)
                self._process_state_data(state_data, managed_resources)
        except Exception as e:
            self.console.print(
                f"[yellow]Error processing Terraform state file {state_file}: {str(e)}"
            )

    def _process_state_data(
        self, state_data: Dict[str, Any], managed_resources: Set[str]
    ) -> None:
        """Process Terraform state data and extract ARNs, including modules"""
        # Process root level resources
        for resource in state_data.get("resources", []):
            # Skip data sources
            if resource.get("mode") == "data":
                continue

            # Process module resources
            if resource.get("module"):
                self._process_module_resource(resource, managed_resources)
            else:
                self._process_resource(resource, managed_resources)

    def _process_module_resource(
        self, resource: Dict[str, Any], managed_resources: Set[str]
    ) -> None:
        """Process a module resource and extract ARNs"""
        module_path = resource.get("module", "")

        try:
            for instance in resource.get("instances", []):
                if "attributes" in instance:
                    attributes = instance["attributes"]
                    if "arn" in attributes:
                        arn = attributes["arn"]
                        managed_resources.add(arn)
                    self._extract_nested_arns(attributes, managed_resources)
        except Exception as e:
            self.console.print(
                f"[yellow]Error processing module {module_path}: {str(e)}"
            )

    def _process_resource(
        self, resource: Dict[str, Any], managed_resources: Set[str]
    ) -> None:
        """Process a root level resource and extract ARNs"""
        try:
            resource_type = (
                f"{resource.get('type', 'unknown')}.{resource.get('name', 'unknown')}"
            )

            for instance in resource.get("instances", []):
                if "attributes" in instance:
                    attributes = instance["attributes"]

                    if "arn" in attributes:
                        arn = attributes["arn"]
                        managed_resources.add(arn)

                    if "id" in attributes and not "arn" in attributes:
                        resource_id = attributes["id"]
                        constructed_arn = self._construct_arn_from_id(
                            resource_type, resource_id
                        )
                        if constructed_arn:
                            managed_resources.add(constructed_arn)
                            self.console.print(
                                f"[cyan]Constructed ARN for {resource_type}: {constructed_arn}"
                            )

                    self._extract_nested_arns(attributes, managed_resources)
        except Exception as e:
            self.console.print(
                f"[yellow]Error processing resource {resource.get('type', 'unknown')}: {str(e)}"
            )

    def _extract_nested_arns(self, attributes: Dict[str, Any], arns: Set[str]) -> None:
        """Recursively extract ARNs from nested attribute structures"""
        for key, value in attributes.items():
            if isinstance(value, str) and ":arn:" in value:
                arns.add(value)
            elif isinstance(value, dict):
                self._extract_nested_arns(value, arns)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._extract_nested_arns(item, arns)

    def _construct_arn_from_id(
        self, resource_type: str, resource_id: str
    ) -> Optional[str]:
        """Construct ARN from resource type and ID when ARN is not directly available"""
        if resource_type.startswith("aws_"):
            resource_type = resource_type[4:]

        arn_patterns = {
            "security_group": "arn:aws:ec2:{region}:{account}:security-group/{id}",
            "subnet": "arn:aws:ec2:{region}:{account}:subnet/{id}",
            "vpc": "arn:aws:ec2:{region}:{account}:vpc/{id}",
            "route_table": "arn:aws:ec2:{region}:{account}:route-table/{id}",
            "internet_gateway": "arn:aws:ec2:{region}:{account}:internet-gateway/{id}",
            "nat_gateway": "arn:aws:ec2:{region}:{account}:nat-gateway/{id}",
            "network_interface": "arn:aws:ec2:{region}:{account}:network-interface/{id}",
        }

        base_type = resource_type.split(".")[-1]
        if base_type in arn_patterns:
            pattern = arn_patterns[base_type]
            return pattern.format(
                region=self.session.region_name,
                account=self.session.client("sts").get_caller_identity()["Account"],
                id=resource_id,
            )

        return None
