# terraform_aws_migrator/generators/aws_network/vpc.py

from typing import Dict, Any, Optional, List
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class VPCGenerator(HCLGenerator):
    """Generator for aws_vpc resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_vpc"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        vpc_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"vpc_{vpc_id.replace('-', '_').lower()}"

    def _format_cidr_blocks(self, cidr_blocks: List[Dict[str, Any]]) -> List[str]:
        """Format CIDR block configurations"""
        formatted = []
        for cidr in cidr_blocks:
            block = []
            if primary := cidr.get("primary", False):
                block.append(f'    primary = {str(primary).lower()}')
            if cidr_block := cidr.get("cidr_block"):
                block.append(f'    cidr_block = "{cidr_block}"')
            if tenant_id := cidr.get("tenant_id"):
                block.append(f'    tenant_id = "{tenant_id}"')
            
            if block:
                formatted.extend(['  cidr_block_association {'] + block + ['  }'])
        return formatted

    def generate(self, resource: Dict[str, Any], include_default: bool = False) -> Optional[str]:
        try:
            vpc_id = resource.get("id")
            details = resource.get("details", {})

            if not vpc_id or not details:
                logger.error(f"Missing required VPC details for VPC {vpc_id}")
                logger.error(f"Resource: {resource}")
                return None

            # Skip default VPC unless specifically requested
            if details.get("is_default", False) and not include_default:
                logger.info(f"Skipping default VPC: {vpc_id}. Use --include-default-vpc flag to include it.")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_vpc" "{resource_name}" {{',
                f'  cidr_block = "{details["cidr_block"]}"'
            ]

            # Add instance tenancy
            instance_tenancy = details.get("instance_tenancy", "default")
            hcl.append(f'  instance_tenancy = "{instance_tenancy}"')

            # Add DNS settings
            enable_dns_support = details.get("enable_dns_support", True)
            enable_dns_hostnames = details.get("enable_dns_hostnames", False)
            hcl.append(f'  enable_dns_support = {str(enable_dns_support).lower()}')
            hcl.append(f'  enable_dns_hostnames = {str(enable_dns_hostnames).lower()}')

            # Add secondary CIDR blocks if present
            if secondary_cidrs := details.get("cidr_block_associations", []):
                for cidr in secondary_cidrs:
                    if not cidr.get("primary", False):  # Skip primary CIDR as it's already added
                        hcl.append(f'  secondary_cidr_blocks = ["{cidr["cidr_block"]}"]')

            # Add IPv6 settings if present
            if ipv6_cidr := details.get("ipv6_cidr_block"):
                hcl.append(f'  assign_generated_ipv6_cidr_block = true')
                hcl.append(f'  ipv6_cidr_block = "{ipv6_cidr}"')

                if ipv6_association_id := details.get("ipv6_association_id"):
                    hcl.append(f'  # IPv6 association ID: {ipv6_association_id}')

            # Add DHCP options association if present
            dhcp_options_id = details.get("dhcp_options_id")

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    key = tag.get("Key", "").replace('"', '\\"')
                    value = tag.get("Value", "").replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Add enable_network_address_usage_metrics if present
            if enable_metrics := details.get("enable_network_address_usage_metrics"):
                hcl.append(f'  enable_network_address_usage_metrics = {str(enable_metrics).lower()}')

            # Add Classic Link settings if present
            if enable_classiclink := details.get("enable_classiclink"):
                hcl.append(f'  enable_classiclink = {str(enable_classiclink).lower()}')
            
            if enable_classiclink_dns := details.get("enable_classiclink_dns_support"):
                hcl.append(f'  enable_classiclink_dns_support = {str(enable_classiclink_dns).lower()}')

            # Close resource block
            hcl.append("}")

            # Add any required VPC-specific configurations
            # For example, VPC Flow Logs if enabled
            if flow_logs := details.get("flow_logs", []):
                for i, log in enumerate(flow_logs):
                    hcl.extend([
                        "",
                        f'resource "aws_flow_log" "{resource_name}_flow_log_{i + 1}" {{',
                        f'  vpc_id = aws_vpc.{resource_name}.id',
                        f'  traffic_type = "{log.get("traffic_type", "ALL")}"',
                        f'  log_destination_type = "{log.get("log_destination_type", "cloud-watch-logs")}"'
                    ])

                    if destination := log.get("log_destination"):
                        hcl.append(f'  log_destination = "{destination}"')

                    if format := log.get("log_format"):
                        hcl.append(f'  log_format = "{format}"')

                    hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for VPC: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            vpc_id = resource.get("id")
            if not vpc_id:
                logger.error("Missing VPC ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()
            commands = [
                f"terraform import {prefix + '.' if prefix else ''}aws_vpc.{resource_name} {vpc_id}"
            ]

            # Add import commands for VPC Flow Logs if present
            details = resource.get("details", {})
            if flow_logs := details.get("flow_logs", []):
                for i, log in enumerate(flow_logs):
                    if log_id := log.get("id"):
                        commands.append(
                            f"terraform import {prefix + '.' if prefix else ''}"
                            f"aws_flow_log.{resource_name}_flow_log_{i + 1} {log_id}"
                        )

            return "\n".join(commands)

        except Exception as e:
            logger.error(f"Error generating import command for VPC: {str(e)}")
            return None
