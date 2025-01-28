# terraform_aws_migrator/state_reader.py

import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
import boto3
import hcl2
from rich.console import Console
import logging
import traceback

logger = logging.getLogger(__name__)


class TerraformStateReader:
    """Handler for reading and processing Terraform state files"""

    def __init__(self, session: boto3.Session):
        self.session = session
        self.console = Console()
        self._account_id = None

    @property
    def account_id(self):
        if not self._account_id:
            self._account_id = self.session.client("sts").get_caller_identity()[
                "Account"
            ]
        return self._account_id

    def read_backend_config(self, tf_dir: str, progress=None) -> List[Dict[str, Any]]:
        """Reads backend configuration from Terraform files"""
        tf_dir_path = Path(tf_dir)
        backend_config = self._find_s3_backend(tf_dir_path)
        return [{"s3": backend_config}] if backend_config else []

    def _extract_resources_from_state(
        self, state_data: Dict[str, Any], managed_resources: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Extract resource information from state data
        Args:
            state_data: Terraform state data
            managed_resources: Dictionary to store managed resource information
        """
        try:
            if "resources" not in state_data:
                return

            for resource in state_data["resources"]:
                if resource.get("mode") == "data":
                    continue

                resource_type = resource.get("type", "")
                for instance in resource.get("instances", []):
                    attributes = instance.get("attributes", {})

                    if resource_type == "aws_iam_role_policy_attachment":
                        role_name = attributes.get("role")
                        policy_arn = attributes.get("policy_arn")
                        if role_name and policy_arn:
                            identifier = f"arn:aws:iam::{self.account_id}:role/{role_name}/{policy_arn}"
                            managed_resources[identifier] = {
                                "id": identifier,
                                "type": resource_type,
                                "role_name": role_name,
                                "policy_arn": policy_arn,
                            }
                    elif resource_type == "aws_iam_user_policy":
                        user_name = attributes.get("user")
                        policy_name = attributes.get("name")
                        if user_name and policy_name:
                            identifier = f"{user_name}:{policy_name}"
                            managed_resources[identifier] = {
                                "id": attributes.get('id', ''),
                                "type": resource_type,
                                "user_name": user_name,
                            }
                    elif resource_type == "aws_iam_user_policy_attachment":
                        user_name = attributes.get("user")
                        policy_arn = attributes.get("policy_arn")
                        if user_name and policy_arn:
                            identifier = f"{user_name}:{policy_arn}"
                            managed_resources[identifier] = {
                                "id": identifier,
                                "type": resource_type,
                                "user_name": user_name,
                                "policy_arn": policy_arn,
                            }
                    else:
                        formatted_resource = self._format_resource(
                            resource_type,
                            attributes,
                            instance.get("index_key"),
                        )
                        if formatted_resource:
                            identifier = self._get_identifier_for_managed_set(
                                formatted_resource
                            )
                            if identifier:
                                managed_resources[identifier] = formatted_resource

        except Exception as e:
            logger.error(f"Error extracting resources from state: {str(e)}")
            raise

    def _get_identifier_for_managed_set(
        self, resource: Dict[str, Any]
    ) -> Optional[str]:
        """
        Get the appropriate identifier for the managed_resources set
        Args:
            resource: Formatted resource dictionary
        Returns:
            String identifier for the managed_resources set
        """
        # Return ARN if available
        if "arn" in resource:
            return resource["arn"]

        # If no ARN, construct identifier from type and id
        resource_type = resource.get("type")
        resource_id = resource.get("id")

        if resource_type and resource_id:
            return f"{resource_type}:{resource_id}"

        return resource.get("id")  # Fallback to just ID if nothing else available

    def _format_resource(
        self, resource_type: str, attributes: Dict[str, Any], index_key: Any = None
    ) -> Optional[Dict[str, Any]]:
        """Format a single resource into our expected structure"""
        try:
            resource_id = self._get_resource_id(resource_type, attributes, index_key)
            if not resource_id:
                return None

            formatted = {
                "id": resource_id,
                "type": resource_type,
                "tags": self._extract_tags(attributes),
                "details": {},
            }

            # Add ARN if available
            if "arn" in attributes:
                formatted["arn"] = attributes["arn"]
            elif resource_type.startswith("aws_iam_"):
                formatted["arn"] = (
                    f"arn:aws:iam::{self.account_id}:{resource_type.replace('aws_', '')}/{resource_id}"
                )

            # Add resource-specific details
            if resource_type == "aws_vpc":
                formatted["details"].update({
                    "cidr_block": attributes.get("cidr_block"),
                    "instance_tenancy": attributes.get("instance_tenancy", "default"),
                    "enable_dns_support": attributes.get("enable_dns_support", True),
                    "enable_dns_hostnames": attributes.get("enable_dns_hostnames", False),
                    "is_default": attributes.get("is_default", False),
                    "cidr_block_associations": attributes.get("cidr_block_associations", []),
                    "ipv6_cidr_block": attributes.get("ipv6_cidr_block"),
                    "ipv6_association_id": attributes.get("ipv6_association_id"),
                    "dhcp_options_id": attributes.get("dhcp_options_id"),
                    "enable_network_address_usage_metrics": attributes.get("enable_network_address_usage_metrics", False)
                })
            elif resource_type == "aws_iam_role":
                formatted["details"].update({
                    "path": attributes.get("path", "/"),
                    "assume_role_policy": json.loads(
                        attributes.get("assume_role_policy", "{}")
                    ),
                    "description": attributes.get("description", ""),
                    "max_session_duration": attributes.get("max_session_duration"),
                    "permissions_boundary": attributes.get("permissions_boundary"),
                })
            elif resource_type == "aws_iam_role_policy_attachment":
                formatted["details"].update({
                    "role": attributes.get("role"),
                    "policy_arn": attributes.get("policy_arn"),
                })

            return formatted

        except Exception as e:
            logger.error(f"Error formatting resource {resource_type}: {str(e)}")
            return None

    def _get_resource_id(
        self, resource_type: str, attributes: Dict[str, Any], index_key: Any = None
    ) -> Optional[str]:
        """Get the appropriate identifier for a resource"""
        if "id" in attributes:
            return attributes["id"]
        elif "name" in attributes:
            return attributes["name"]
        return None

    def _extract_tags(self, attributes: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract tags from attributes in a consistent format"""
        tags: List[Dict[str, str]] = []
        if "tags" in attributes:
            if isinstance(attributes["tags"], dict):
                tags.extend(
                    {"Key": k, "Value": str(v)} for k, v in attributes["tags"].items()
                )
            elif isinstance(attributes["tags"], list):
                tags.extend(attributes["tags"])
        return tags

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

    # terraform_aws_migrator/state_reader.py

    def get_managed_resources(
        self, tf_dir: str, progress=None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all resources managed by Terraform from state files with their complete information

        Args:
            tf_dir: Directory containing Terraform files
            progress: Optional progress callback

        Returns:
            Dictionary of managed resources with their complete information
            Format:
            {
                "resource_identifier": {
                    "id": "example_id",
                    "type": "aws_iam_role",
                    "arn": "arn:aws:iam::...",
                    "tags": [...],
                    "details": {...}
                },
                ...
            }
        """
        managed_resources: Dict[str, Dict[str, Any]] = {}
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
                    try:
                        self._extract_resources_from_state(state_data, managed_resources)
                    except Exception as e:
                        logger.error(f"Error processing S3 state: {str(e)}")

            # Then check local state files
            state_files = list(Path(tf_dir).rglob("*.tfstate"))
            for state_file in state_files:
                state_data = self._read_local_state(state_file)
                if state_data:
                    try:
                        self._extract_resources_from_state(state_data, managed_resources)
                    except Exception as e:
                        logger.error(f"Error processing local state {state_file}: {str(e)}")

            return managed_resources

        except Exception as e:
            self.console.print(f"[red]Error reading Terraform state: {str(e)}")
            return {}

    def _extract_resources_from_state(
        self, state_data: Dict[str, Any], managed_resources: Dict[str, Dict[str, Any]]
    ):
        """
        Extract resource information from state data

        Args:
            state_data: Terraform state data
            managed_resources: Dictionary to store managed resource information
        """
        try:
            if "resources" not in state_data:
                return

            for resource in state_data["resources"]:
                if resource.get("mode") == "data":
                    continue

                resource_type = resource.get("type", "")
                for instance in resource.get("instances", []):
                    attributes = instance.get("attributes", {})

                    if resource_type == "aws_iam_role_policy_attachment":
                        role_name = attributes.get("role")
                        policy_arn = attributes.get("policy_arn")
                        if role_name and policy_arn:
                            identifier = f"arn:aws:iam::{self.account_id}:role/{role_name}/{policy_arn}"
                            managed_resources[identifier] = {
                                "id": identifier,
                                "type": resource_type,
                                "role_name": role_name,
                                "policy_arn": policy_arn,
                            }
                    elif resource_type == "aws_iam_user_policy":
                        user_name = attributes.get("user")
                        policy_name = attributes.get("name")
                        identifier = f"{user_name}:{policy_name}"
                        managed_resources[identifier] = {
                            "id": attributes['id'],
                            "type": resource_type,
                            "user_name": user_name,
                        }
                    elif resource_type == "aws_iam_user_policy_attachment":
                        user_name = attributes.get("user")
                        policy_arn = attributes.get("policy_arn")
                        identifier = f"{user_name}:{policy_arn}"
                        managed_resources[identifier] = {
                            "id": identifier,
                            "type": resource_type,
                            "user_name": user_name,
                            "policy_arn": policy_arn,
                        }
                    else:
                        formatted_resource = self._format_resource(
                            resource_type,
                            attributes,
                            instance.get("index_key"),
                        )
                        if formatted_resource:
                            identifier = self._get_identifier_for_managed_set(
                                formatted_resource
                            )
                            if identifier:
                                managed_resources[identifier] = formatted_resource

        except Exception as e:
            raise e

    def get_s3_state_file(
        self, bucket: str, key: str, region: str, progress=None
    ) -> Dict[str, Any]:
        """Read Terraform state file from S3 (for backward compatibility)"""
        return self._get_s3_state(bucket, key, region) or {}

