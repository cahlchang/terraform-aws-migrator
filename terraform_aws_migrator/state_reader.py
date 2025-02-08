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
                # Skip data sources and non-managed mode resources
                if resource.get("mode") != "managed":
                    continue
                
                # Check if resource is part of a module
                module_path = resource.get("module", "")
                resource_type = resource.get("type", "")
                for instance in resource.get("instances", []):
                    try:
                        attributes = instance.get("attributes", {})
                        identifier = None
                        resource_info = None
            
                        if resource_type == "aws_iam_role_policy_attachment":
                            role_name = attributes.get("role")
                            policy_arn = attributes.get("policy_arn")
                            if role_name and policy_arn:
                                identifier = f"arn:aws:iam::{self.account_id}:role/{role_name}/{policy_arn}"
                                resource_info = {
                                    "id": identifier,
                                    "type": resource_type,
                                    "role_name": role_name,
                                    "policy_arn": policy_arn,
                                    "managed": True
                                }
                        elif resource_type == "aws_iam_user_policy":
                            user_name = attributes.get("user")
                            policy_name = attributes.get("name")
                            if user_name and policy_name:
                                identifier = f"{user_name}:{policy_name}"
                                resource_info = {
                                    "id": attributes.get('id', ''),
                                    "type": resource_type,
                                    "user_name": user_name,
                                    "managed": True
                                }
                        elif resource_type == "aws_iam_user_policy_attachment":
                            user_name = attributes.get("user")
                            policy_arn = attributes.get("policy_arn")
                            if user_name and policy_arn:
                                identifier = f"{user_name}:{policy_arn}"
                                resource_info = {
                                    "id": identifier,
                                    "type": resource_type,
                                    "user_name": user_name,
                                    "policy_arn": policy_arn,
                                    "managed": True
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
                                    resource_info = formatted_resource
                                    resource_info["managed"] = True

                        if identifier and resource_info:
                            if identifier not in managed_resources:
                                managed_resources[identifier] = resource_info
                            else:
                                logger.debug(f"Skipping duplicate resource: {identifier}")

                    except Exception as e:
                        logger.error(f"Error processing instance in resource {resource_type}: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Error extracting resources from state: {str(e)}")
            logger.debug(traceback.format_exc())

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
        # Use ARN if available
        if "arn" in resource:
            return resource["arn"]

        resource_type = resource.get("type")
        resource_id = resource.get("id")

        # Special handling for IAM resources
        if resource_type and resource_type.startswith("aws_iam_"):
            if resource_type == "aws_iam_role_policy_attachment":
                role_name = resource.get("role")
                policy_arn = resource.get("policy_arn")
                if role_name and policy_arn:
                    return f"arn:aws:iam::{self.account_id}:role/{role_name}/{policy_arn}"
            elif resource_type == "aws_iam_user_policy":
                user_name = resource.get("user")
                policy_name = resource.get("name")
                if user_name and policy_name:
                    return f"{user_name}:{policy_name}"
            elif resource_type == "aws_iam_user_policy_attachment":
                user_name = resource.get("user")
                policy_arn = resource.get("policy_arn")
                if user_name and policy_arn:
                    return f"{user_name}:{policy_arn}"

        # Basic identifier generation
        if resource_type and resource_id:
            return f"{resource_type}:{resource_id}"

        return resource.get("id")

    def _format_resource(
        self, resource_type: str, attributes: Dict[str, Any], index_key: Any = None
    ) -> Optional[Dict[str, Any]]:
        """Format a single resource into our expected structure"""
        try:
            resource_id = self._get_resource_id(resource_type, attributes, index_key)
            if not resource_id:
                return None

            formatted: Dict[str, Any] = {
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
                formatted["details"] = {
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
                }
            elif resource_type == "aws_subnet":
                formatted["details"] = {
                    "vpc_id": attributes.get("vpc_id"),
                    "cidr_block": attributes.get("cidr_block"),
                    "availability_zone": attributes.get("availability_zone"),
                    "map_public_ip_on_launch": attributes.get("map_public_ip_on_launch", False),
                    "assign_ipv6_address_on_creation": attributes.get("assign_ipv6_address_on_creation", False),
                    "ipv6_cidr_block": attributes.get("ipv6_cidr_block"),
                    "enable_dns64": attributes.get("enable_dns64", False),
                    "enable_resource_name_dns_aaaa_record_on_launch": attributes.get("enable_resource_name_dns_aaaa_record_on_launch", False),
                    "enable_resource_name_dns_a_record_on_launch": attributes.get("enable_resource_name_dns_a_record_on_launch", False),
                    "private_dns_hostname_type_on_launch": attributes.get("private_dns_hostname_type_on_launch", "ip-name")
                }
            elif resource_type == "aws_iam_role":
                formatted["details"] = {
                    "path": attributes.get("path", "/"),
                    "assume_role_policy": json.loads(
                        attributes.get("assume_role_policy", "{}")
                    ),
                    "description": attributes.get("description", ""),
                    "max_session_duration": attributes.get("max_session_duration"),
                    "permissions_boundary": attributes.get("permissions_boundary"),
                }
            elif resource_type == "aws_iam_role_policy_attachment":
                formatted["details"] = {
                    "role": attributes.get("role"),
                    "policy_arn": attributes.get("policy_arn"),
                }

            # Add all attributes to details (don't overwrite existing values)
            for key, value in attributes.items():
                if key not in ["id", "arn", "tags"] and key not in formatted["details"]:
                    formatted["details"][key] = value

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
        """Find S3 backend configuration in Terraform files"""
        try:
            # Check all .tf files in the directory
            for tf_file in tf_dir.glob("*.tf"):
                try:
                    with open(tf_file) as f:
                        content = hcl2.load(f)
                        if "terraform" not in content:
                            continue

                        for terraform_block in content["terraform"]:
                            if "backend" not in terraform_block:
                                continue

                            backend = terraform_block["backend"]
                            if not isinstance(backend, list):
                                continue

                            for backend_config in backend:
                                if "s3" in backend_config:
                                    logger.debug(f"Found S3 backend configuration in {tf_file}")
                                    return backend_config["s3"]

                except Exception as e:
                    logger.warning(f"Error reading {tf_file}: {str(e)}")
                    continue

            logger.debug("No S3 backend configuration found")
            return None

        except Exception as e:
            logger.error(f"Error searching for S3 backend: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    def _get_s3_state(
        self, bucket: str, key: str, region: str
    ) -> Optional[Dict[str, Any]]:
        """Read Terraform state file from S3"""
        try:
            s3_client = self.session.client("s3", region_name=region)
            
            # Check if object exists
            try:
                head = s3_client.head_object(Bucket=bucket, Key=key)
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    logger.warning(f"State file does not exist in S3: s3://{bucket}/{key}")
                    return None
                raise

            # Check file size
            content_length = int(head['ContentLength'])
            size_mb = content_length / (1024 * 1024)
            if size_mb > 100:
                logger.warning(f"S3 state file is very large ({size_mb:.2f}MB): s3://{bucket}/{key}")

            # Get the object
            response = s3_client.get_object(Bucket=bucket, Key=key)
            
            try:
                # S3のレスポンスボディを取得
                body = response["Body"]
                # readメソッドを呼び出してデータを取得
                content = body.read()
                # バイト列の場合はデコード
                if isinstance(content, (bytes, bytearray)):
                    content = content.decode("utf-8")
                elif isinstance(content, str):
                    pass
                else:
                    # その他の場合（モックなど）は文字列として扱う
                    content = str(content)
                # JSONとしてパース
                state_data = json.loads(content)
                if not isinstance(state_data, dict):
                    logger.warning(f"Invalid state file format (not a dictionary): s3://{bucket}/{key}")
                    return None
                
                # Basic validation of state file structure
                if "version" not in state_data:
                    logger.warning(f"State file missing version field: s3://{bucket}/{key}")
                    return None

                logger.debug(f"Successfully read state file from S3: s3://{bucket}/{key}")
                return state_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in S3 state file s3://{bucket}/{key}: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Error reading state file from S3 s3://{bucket}/{key}: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    def _read_local_state(self, state_file: Path) -> Optional[Dict[str, Any]]:
        """Read a local Terraform state file"""
        try:
            if not state_file.exists():
                logger.warning(f"State file does not exist: {state_file}")
                return None

            if state_file.stat().st_size == 0:
                logger.warning(f"State file is empty: {state_file}")
                return None

            # Check if file is too large (> 100MB)
            if state_file.stat().st_size > 100 * 1024 * 1024:
                logger.warning(f"State file is very large ({state_file.stat().st_size / 1024 / 1024:.2f}MB): {state_file}")

            with open(state_file) as f:
                try:
                    state_data = json.load(f)
                    if not isinstance(state_data, dict):
                        logger.warning(f"Invalid state file format (not a dictionary): {state_file}")
                        return None
                    
                    # Basic validation of state file structure
                    if "version" not in state_data:
                        logger.warning(f"State file missing version field: {state_file}")
                        return None

                    logger.debug(f"Successfully read state file: {state_file}")
                    return state_data
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in state file {state_file}: {str(e)}")
                    return None

        except Exception as e:
            logger.error(f"Error reading state file {state_file}: {str(e)}")
            logger.debug(traceback.format_exc())
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
                    "details": {...},
                    "managed": True
                },
                ...
            }
        """
        managed_resources: Dict[str, Dict[str, Any]] = {}
        tf_dir_path = Path(tf_dir)
        processed_states = set()  # Track processed state files to avoid duplicates

        try:
            # First check S3 backend
            s3_config = self._find_s3_backend(tf_dir_path)
            if s3_config:
                state_data = self._get_s3_state(
                    bucket=s3_config["bucket"],
                    key=s3_config["key"],
                    region=s3_config.get("region", self.session.region_name),
                )
                if state_data:
                    try:
                        self._extract_resources_from_state(state_data, managed_resources)
                        processed_states.add(s3_config["key"])
                    except Exception as e:
                        logger.error(f"Error processing S3 state: {str(e)}")
                        logger.debug(traceback.format_exc())

            # Then check local state files
            state_files = list(Path(tf_dir).rglob("*.tfstate"))
            for state_file in state_files:
                if str(state_file) in processed_states:
                    logger.debug(f"Skipping already processed state file: {state_file}")
                    continue

                state_data = self._read_local_state(state_file)
                if state_data:
                    try:
                        self._extract_resources_from_state(state_data, managed_resources)
                        processed_states.add(str(state_file))
                    except Exception as e:
                        logger.error(f"Error processing local state {state_file}: {str(e)}")
                        logger.debug(traceback.format_exc())

            logger.info(f"Processed {len(processed_states)} state files")
            logger.info(f"Found {len(managed_resources)} managed resources")
            return managed_resources

        except Exception as e:
            logger.error(f"Error reading Terraform state: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}

    def get_s3_state_file(
        self, bucket: str, key: str, region: str, progress=None
    ) -> Dict[str, Any]:
        """Read Terraform state file from S3 (for backward compatibility)"""
        return self._get_s3_state(bucket, key, region) or {}
