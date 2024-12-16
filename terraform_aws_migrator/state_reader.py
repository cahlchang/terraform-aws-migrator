# terraform_aws_migrator/state_reader.py

import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
import boto3
import hcl2
from rich.console import Console


class TerraformStateReader:
    """Handler for reading and processing Terraform state files"""

    def __init__(self, session: boto3.Session):
        self.session = session
        self.console = Console()

    def read_backend_config(self, tf_dir: str, progress=None) -> List[Dict[str, Any]]:
        """Reads backend configuration from Terraform files (for backward compatibility)"""
        tf_dir_path = Path(tf_dir)
        backend_config = self._find_s3_backend(tf_dir_path)
        return [{"s3": backend_config}] if backend_config else []

    def get_managed_resources(self, tf_dir: str, progress=None) -> Set[str]:
        """Get all ARNs of resources managed by Terraform from state files"""
        managed_resources = set()
        tf_dir_path = Path(tf_dir)
        try:
            # First check S3 backend
            s3_config = self._find_s3_backend(tf_dir_path)
            if s3_config and progress:
                state_data = self._get_s3_state(
                    bucket=s3_config["bucket"],
                    key=s3_config["key"],
                    region=s3_config.get("region", self.session.region_name),
                )
                if state_data:
                    self._extract_resources_from_state(state_data, managed_resources)

            # Then check local state files
            state_files = list(Path(tf_dir).rglob("*.tfstate"))
            for state_file in state_files:
                state_data = self._read_local_state(state_file)
                if state_data:
                    self._extract_resources_from_state(state_data, managed_resources)

            return managed_resources
        except Exception as e:
            self.console.print(f"[red]Error reading Terraform state: {str(e)}")
            return set()

    def get_s3_state_file(
        self, bucket: str, key: str, region: str, progress=None
    ) -> Dict[str, Any]:
        """Read Terraform state file from S3 (for backward compatibility)"""
        return self._get_s3_state(bucket, key, region) or {}

    def read_backend_config(self, tf_dir: str, progress=None) -> List[Dict[str, Any]]:
        """Reads backend configuration from Terraform files (for backward compatibility)"""
        tf_dir_path = Path(tf_dir)
        backend_config = self._find_s3_backend(tf_dir_path)
        return [{"s3": backend_config}] if backend_config else []

    def _find_s3_backend(self, tf_dir: Path) -> Optional[Dict[str, str]]:
        """Find S3 backend configuration in main.tf"""
        main_tf = tf_dir / "main.tf"
        if not main_tf.exists():
            return None

        try:
            with open(main_tf) as f:
                content = hcl2.load(f)
                if "terraform" not in content:
                    return None

                for terraform_block in content["terraform"]:
                    if "backend" not in terraform_block:
                        continue

                    backend = terraform_block["backend"]
                    if not isinstance(backend, list):
                        continue

                    for backend_config in backend:
                        if "s3" in backend_config:
                            return backend_config["s3"]
        except Exception as e:
            self.console.print(f"[yellow]Error reading main.tf: {str(e)}")
            return None

        return None

    def _get_s3_state(
        self, bucket: str, key: str, region: str
    ) -> Optional[Dict[str, Any]]:
        """Read Terraform state file from S3"""
        try:
            s3_client = self.session.client("s3", region_name=region)
            response = s3_client.get_object(Bucket=bucket, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except Exception as e:
            self.console.print(
                f"[red]Error reading state file from S3 {bucket}/{key}: {str(e)}"
            )
            return None

    def _read_local_state(self, state_file: Path) -> Optional[Dict[str, Any]]:
        """Read a local Terraform state file"""
        try:
            with open(state_file) as f:
                return json.load(f)
        except Exception as e:
            self.console.print(
                f"[yellow]Error reading state file {state_file}: {str(e)}"
            )
            return None

    def _extract_resources_from_state(
        self, state_data: Dict[str, Any], managed_resources: Set[str]
    ):
        """Extract resource identifiers from state data"""
        # For Terraform 0.13+ format
        if "resources" in state_data:
            for resource in state_data["resources"]:
                # Skip data sources
                if resource.get("mode") == "data":
                    continue

                for instance in resource.get("instances", []):
                    attributes = instance.get("attributes", {})
                    self._add_resource_identifier(attributes, managed_resources)

        # For older state format
        if "modules" in state_data:
            for module in state_data["modules"]:
                resources = module.get("resources", {})
                for resource_addr, resource in resources.items():
                    # Skip data sources
                    if resource_addr.startswith("data."):
                        continue

                    primary = resource.get("primary", {})
                    attributes = primary.get("attributes", {})
                    self._add_resource_identifier(attributes, managed_resources)

    def _add_resource_identifier(
        self, attributes: Dict[str, Any], managed_resources: Set[str]
    ):
        """Add resource identifier (ARN or constructed identifier) to the set"""
        if "arn" in attributes:
            managed_resources.add(attributes["arn"])
            return

        if "id" in attributes and "type" in attributes:
            constructed_id = f"{attributes['type']}:{attributes['id']}"
            managed_resources.add(constructed_id)
            return

        if "id" in attributes:
            managed_resources.add(attributes["id"])
