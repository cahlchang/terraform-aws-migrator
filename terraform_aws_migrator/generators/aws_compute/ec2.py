# terraform_aws_migrator/generators/aws_compute/ec2.py

from typing import Dict, List, Any, Optional
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class EC2InstanceGenerator(HCLGenerator):
    """Generator for aws_instance resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_instance"

    def _get_name_from_tags(self, tags: List[Dict[str, str]]) -> Optional[str]:
        """Get Name tag value from tags list"""
        for tag in tags:
            if isinstance(tag, dict) and tag.get("Key") == "Name":
                return tag.get("Value")
        return None

    def _get_short_instance_id(self, instance_id: str) -> str:
        """Get shortened version of instance ID (last 4 characters)"""
        return instance_id[-4:] if instance_id else ""

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from Name tag or instance ID"""
        instance_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = self._get_name_from_tags(tags)
        short_id = self._get_short_instance_id(instance_id)

        if name_tag:
            # If there's a Name tag, use it with the short instance ID as suffix
            base_name = name_tag.replace("-", "_").replace(" ", "_")
            return f"{base_name}_{short_id}"
        else:
            # Fallback to instance ID if no Name tag
            return instance_id.replace("-", "_")

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for an EC2 instance"""
        try:
            instance_id = resource.get("id")
            if not instance_id:
                logger.error("Missing required instance ID")
                return None

            # Generate resource name based on Name tag or instance ID
            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_instance" "{resource_name}" {{',
            ]

            # Add instance details if available
            details = resource.get("details", {})

            # Add required fields with fallback values
            if details.get("ami"):
                hcl.append(f'  ami = "{details["ami"]}"')

            if details.get("instance_type"):
                hcl.append(f'  instance_type = "{details["instance_type"]}"')

            # Add optional fields if present
            if details.get("availability_zone"):
                hcl.append(f'  availability_zone = "{details["availability_zone"]}"')

            if details.get("subnet_id"):
                hcl.append(f'  subnet_id = "{details["subnet_id"]}"')

            if details.get("key_name"):
                hcl.append(f'  key_name = "{details["key_name"]}"')

            # Add VPC security groups if present
            vpc_security_groups = details.get("vpc_security_group_ids", [])
            if vpc_security_groups:
                security_groups_str = '", "'.join(vpc_security_groups)
                hcl.append(f'  vpc_security_group_ids = ["{security_groups_str}"]')

            # Add IAM instance profile if present
            if details.get("iam_instance_profile"):
                hcl.append(f'  iam_instance_profile = "{details["iam_instance_profile"]}"')

            # Add monitoring configuration
            monitoring = details.get("monitoring", False)
            hcl.append(f"  monitoring = {str(monitoring).lower()}")

            # Add root block device if present
            root_block_device = details.get("root_block_device")
            if root_block_device:
                hcl.extend([
                    "  root_block_device {",
                    f'    volume_size = {root_block_device.get("volume_size", 8)}',
                    f'    volume_type = "{root_block_device.get("volume_type", "gp2")}"',
                    f'    encrypted = {str(root_block_device.get("encrypted", False)).lower()}',
                    "  }",
                ])

            # Add EBS block devices if present
            ebs_block_devices = details.get("ebs_block_device", [])
            for device in ebs_block_devices:
                hcl.extend([
                    "  ebs_block_device {",
                    f'    device_name = "{device.get("device_name")}"',
                    f'    volume_size = {device.get("volume_size", 8)}',
                    f'    volume_type = "{device.get("volume_type", "gp2")}"',
                    f'    encrypted = {str(device.get("encrypted", False)).lower()}',
                    "  }",
                ])

            # Add user data if present
            user_data = details.get("user_data")
            if user_data:
                hcl.append(f'  user_data = "{user_data}"')

            # Set user_data_replace_on_change to false (Terraform default)
            # This setting determines whether changes to user_data should trigger instance replacement
            hcl.append("  user_data_replace_on_change = false")

            # Add instance tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        key = tag["Key"].replace('"', '\\"')
                        value = tag["Value"].replace('"', '\\"')
                        hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for EC2 instance: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for EC2 instance"""
        try:
            instance_id = resource.get("id")
            if not instance_id:
                logger.error("Missing instance ID for import command")
                return None

            # Generate resource name matching the one in generate()
            resource_name = self._generate_resource_name(resource)

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_instance.{resource_name} {instance_id}"

        except Exception as e:
            logger.error(f"Error generating import command for EC2 instance: {str(e)}")
            return None
