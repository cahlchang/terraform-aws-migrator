# terraform_aws_migrator/generators/aws_network/subnet.py

from typing import Dict, Any, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class SubnetGenerator(HCLGenerator):
    """Generator for aws_subnet resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_subnet"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        subnet_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"subnet_{subnet_id.replace('-', '_').lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            subnet_id = resource.get("id")
            details = resource.get("details", {})

            if not subnet_id or not details:
                logger.error("Missing required subnet details")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_subnet" "{resource_name}" {{',
                f'  vpc_id = "{details["vpc_id"]}"',
                f'  cidr_block = "{details["cidr_block"]}"',
                f'  availability_zone = "{details["availability_zone"]}"'
            ]

            # Add optional fields
            if details.get("ipv6_cidr_block"):
                hcl.append(f'  ipv6_cidr_block = "{details["ipv6_cidr_block"]}"')
                hcl.append(f'  assign_ipv6_address_on_creation = {str(details.get("assign_ipv6_address_on_creation", False)).lower()}')

            # Public IP settings
            hcl.append(f'  map_public_ip_on_launch = {str(details.get("map_public_ip_on_launch", False)).lower()}')

            if details.get("enable_dns64"):
                hcl.append(f'  enable_dns64 = {str(details["enable_dns64"]).lower()}')

            # Add customer owned IPv4 pool if present
            if customer_owned_ipv4_pool := details.get("customer_owned_ipv4_pool"):
                hcl.append(f'  customer_owned_ipv4_pool = "{customer_owned_ipv4_pool}"')
                hcl.append(f'  map_customer_owned_ip_on_launch = {str(details.get("map_customer_owned_ip_on_launch", False)).lower()}')

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
            logger.error(f"Error generating HCL for subnet: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            subnet_id = resource.get("id")
            if not subnet_id:
                logger.error("Missing subnet ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()

            return f"terraform import {prefix + '.' if prefix else ''}aws_subnet.{resource_name} {subnet_id}"

        except Exception as e:
            logger.error(f"Error generating import command for subnet: {str(e)}")
            return None
