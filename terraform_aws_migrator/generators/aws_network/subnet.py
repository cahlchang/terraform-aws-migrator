from typing import Dict, Any, Optional
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

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
            return name_tag.replace("-", "_").replace(" ", "_").replace("/", "_").lower()
        else:
            return f"subnet_{subnet_id.replace('-', '_').lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            subnet_id = resource.get("id")
            details = resource.get("details", {})

            if not subnet_id or not details:
                logger.error(f"Missing required Subnet details for Subnet {subnet_id}")
                return None

            resource_name = self._generate_resource_name(resource)
            vpc_id = details.get("vpc_id")

            # Start building HCL
            hcl = [
                f'resource "aws_subnet" "{resource_name}" {{',
                f'  vpc_id = "{vpc_id}"',
                f'  cidr_block = "{details["cidr_block"]}"',
                f'  availability_zone = "{details.get("availability_zone", "")}"'
            ]

            # Add map_public_ip setting
            map_public_ip = details.get("map_public_ip_on_launch", False)
            hcl.append(f'  map_public_ip_on_launch = {str(map_public_ip).lower()}')

            # Add assign_ipv6_address_on_creation if present
            if ipv6_on_creation := details.get("assign_ipv6_address_on_creation"):
                hcl.append(f'  assign_ipv6_address_on_creation = {str(ipv6_on_creation).lower()}')

            # Add ipv6_cidr_block if present
            if ipv6_cidr := details.get("ipv6_cidr_block"):
                hcl.append(f'  ipv6_cidr_block = "{ipv6_cidr}"')

            # Add enable_dns64 if present
            if enable_dns64 := details.get("enable_dns64"):
                hcl.append(f'  enable_dns64 = {str(enable_dns64).lower()}')

            # Add enable_resource_name_dns_aaaa_record_on_launch if present
            if enable_dns_aaaa := details.get("enable_resource_name_dns_aaaa_record_on_launch"):
                hcl.append(f'  enable_resource_name_dns_aaaa_record_on_launch = {str(enable_dns_aaaa).lower()}')

            # Add enable_resource_name_dns_a_record_on_launch if present
            if enable_dns_a := details.get("enable_resource_name_dns_a_record_on_launch"):
                hcl.append(f'  enable_resource_name_dns_a_record_on_launch = {str(enable_dns_a).lower()}')

            # Add private_dns_hostname_type_on_launch if present
            if hostname_type := details.get("private_dns_hostname_type_on_launch"):
                hcl.append(f'  private_dns_hostname_type_on_launch = "{hostname_type}"')

            # Add customer_owned_ipv4_pool if present
            if ipv4_pool := details.get("customer_owned_ipv4_pool"):
                hcl.append(f'  customer_owned_ipv4_pool = "{ipv4_pool}"')

            # Add outpost_arn if present
            if outpost_arn := details.get("outpost_arn"):
                hcl.append(f'  outpost_arn = "{outpost_arn}"')

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
            logger.error(f"Error generating HCL for Subnet: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            subnet_id = resource.get("id")
            if not subnet_id:
                logger.error("Missing Subnet ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()
            
            return f"terraform import {prefix + '.' if prefix else ''}aws_subnet.{resource_name} {subnet_id}"

        except Exception as e:
            logger.error(f"Error generating import command for Subnet: {str(e)}")
            return None
