# terraform_aws_migrator/generators/aws_network/gateways.py

from typing import Dict, Any, Optional, List
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class InternetGatewayGenerator(HCLGenerator):
    """Generator for aws_internet_gateway resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_internet_gateway"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        igw_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"igw_{igw_id.replace('-', '_').lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            igw_id = resource.get("id")
            details = resource.get("details", {})

            if not igw_id:
                logger.error("Missing required internet gateway ID")
                return None

            resource_name = self._generate_resource_name(resource)
            
            # Start building HCL
            hcl = [
                f'resource "aws_internet_gateway" "{resource_name}" {{',
            ]

            # Add VPC ID if attached
            vpc_attachments = details.get("vpc_attachments", [])
            if vpc_attachments and vpc_attachments[0].get("state") == "available":
                hcl.append(f'  vpc_id = "{vpc_attachments[0]["vpc_id"]}"')

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    key = tag.get("Key", "").replace('"', '\\"')
                    value = tag.get("Value", "").replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for internet gateway: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            igw_id = resource.get("id")
            if not igw_id:
                logger.error("Missing internet gateway ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()

            return f"terraform import {prefix + '.' if prefix else ''}aws_internet_gateway.{resource_name} {igw_id}"

        except Exception as e:
            logger.error(f"Error generating import command for internet gateway: {str(e)}")
            return None


@register_generator
class NATGatewayGenerator(HCLGenerator):
    """Generator for aws_nat_gateway resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_nat_gateway"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        nat_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"nat_{nat_id.replace('-', '_').lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            nat_id = resource.get("id")
            details = resource.get("details", {})

            if not nat_id or not details:
                logger.error("Missing required NAT gateway details")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_nat_gateway" "{resource_name}" {{',
                f'  subnet_id = "{details["subnet_id"]}"',
            ]

            # Add connectivity type
            connectivity_type = details.get("connectivity_type", "public")
            if connectivity_type != "public":
                hcl.append(f'  connectivity_type = "{connectivity_type}"')

            # Add elastic IP allocation for public NAT gateways
            if connectivity_type == "public":
                # Since we can't determine if the EIP was created by Terraform or not,
                # we'll add a comment suggesting manual verification
                hcl.append("  # Note: You may want to manage the allocation_id separately using aws_eip")
                hcl.append(f'  allocation_id = "{details.get("elastic_ip_allocation_id", "")}"')

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    key = tag.get("Key", "").replace('"', '\\"')
                    value = tag.get("Value", "").replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for NAT gateway: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            nat_id = resource.get("id")
            if not nat_id:
                logger.error("Missing NAT gateway ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()

            return f"terraform import {prefix + '.' if prefix else ''}aws_nat_gateway.{resource_name} {nat_id}"

        except Exception as e:
            logger.error(f"Error generating import command for NAT gateway: {str(e)}")
            return None
