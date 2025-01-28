# terraform_aws_migrator/generators/aws_network/nacl_dhcp.py

from typing import Dict, Any, Optional, List
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class NetworkACLGenerator(HCLGenerator):
    """Generator for aws_network_acl resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_network_acl"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        nacl_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"nacl_{nacl_id.replace('-', '_').lower()}"

    def _format_rule(self, rule: Dict[str, Any], is_egress: bool) -> List[str]:
        """Format a single NACL rule"""
        rule_lines = []
        rule_type = "egress" if is_egress else "ingress"

        rule_lines.append(f"  {rule_type} {{")
        rule_lines.append(f"    protocol = {rule['Protocol']}")
        rule_lines.append(f"    rule_no = {rule['RuleNumber']}")
        rule_lines.append(f"    action = \"{rule['RuleAction'].lower()}\"")

        if "CidrBlock" in rule:
            rule_lines.append(f"    cidr_block = \"{rule['CidrBlock']}\"")
        elif "Ipv6CidrBlock" in rule:
            rule_lines.append(f"    ipv6_cidr_block = \"{rule['Ipv6CidrBlock']}\"")

        if rule["Protocol"] not in ["-1", "all"]:
            from_port = rule.get("PortRange", {}).get("From", 0)
            to_port = rule.get("PortRange", {}).get("To", 0)
            rule_lines.append(f"    from_port = {from_port}")
            rule_lines.append(f"    to_port = {to_port}")

        rule_lines.append("  }")
        return rule_lines

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            nacl_id = resource.get("id")
            details = resource.get("details", {})

            if not nacl_id or not details:
                logger.error("Missing required Network ACL details")
                return None

            # Skip default Network ACLs as they're managed by AWS
            if details.get("is_default", False):
                logger.info(f"Skipping default Network ACL: {nacl_id}")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_network_acl" "{resource_name}" {{',
                f'  vpc_id = "{details["vpc_id"]}"'
            ]

            # Add subnet associations
            if associations := details.get("associations", []):
                subnet_ids = [assoc["SubnetId"] for assoc in associations if "SubnetId" in assoc]
                if subnet_ids:
                    subnet_ids_str = '", "'.join(subnet_ids)
                    hcl.append(f'  subnet_ids = ["{subnet_ids_str}"]')

            # Add ingress rules
            for rule in details.get("ingress_rules", []):
                hcl.extend(self._format_rule(rule, is_egress=False))

            # Add egress rules
            for rule in details.get("egress_rules", []):
                hcl.extend(self._format_rule(rule, is_egress=True))

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
            logger.error(f"Error generating HCL for Network ACL: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            nacl_id = resource.get("id")
            if not nacl_id:
                logger.error("Missing Network ACL ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()

            return f"terraform import {prefix + '.' if prefix else ''}aws_network_acl.{resource_name} {nacl_id}"

        except Exception as e:
            logger.error(f"Error generating import command for Network ACL: {str(e)}")
            return None


@register_generator
class DHCPOptionsGenerator(HCLGenerator):
    """Generator for aws_vpc_dhcp_options resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_vpc_dhcp_options"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        dhcp_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"dhcp_{dhcp_id.replace('-', '_').lower()}"

    def _format_list_values(self, values: List[str]) -> str:
        """Format a list of values for HCL"""
        if not values:
            return "[]"
        return '[' + ', '.join(f'"{v}"' for v in values) + ']'

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            dhcp_id = resource.get("id")
            details = resource.get("details", {})

            if not dhcp_id or not details:
                logger.error("Missing required DHCP options details")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_vpc_dhcp_options" "{resource_name}" {{'
            ]

            # Add DHCP options
            if domain_name := details.get("domain_name"):
                hcl.append(f'  domain_name = "{domain_name[0]}"')

            if domain_name_servers := details.get("domain_name_servers"):
                hcl.append(f"  domain_name_servers = {self._format_list_values(domain_name_servers)}")

            if ntp_servers := details.get("ntp_servers"):
                hcl.append(f"  ntp_servers = {self._format_list_values(ntp_servers)}")

            if netbios_name_servers := details.get("netbios_name_servers"):
                hcl.append(f"  netbios_name_servers = {self._format_list_values(netbios_name_servers)}")

            if netbios_node_type := details.get("netbios_node_type"):
                hcl.append(f'  netbios_node_type = "{netbios_node_type[0]}"')

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

            # Add VPC association if this DHCP options set is associated with a VPC
            vpc_id = details.get("vpc_id")
            if vpc_id:
                hcl.extend([
                    "",
                    f'resource "aws_vpc_dhcp_options_association" "{resource_name}_association" {{',
                    f'  vpc_id = "{vpc_id}"',
                    f'  dhcp_options_id = aws_vpc_dhcp_options.{resource_name}.id',
                    "}"
                ])

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for DHCP options: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            dhcp_id = resource.get("id")
            if not dhcp_id:
                logger.error("Missing DHCP options ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()
            commands = [
                f"terraform import {prefix + '.' if prefix else ''}aws_vpc_dhcp_options.{resource_name} {dhcp_id}"
            ]

            # Add import command for VPC association if present
            if vpc_id := resource.get("details", {}).get("vpc_id"):
                commands.append(
                    f"terraform import {prefix + '.' if prefix else ''}aws_vpc_dhcp_options_association.{resource_name}_association {vpc_id}:{dhcp_id}"
                )

            return "\n".join(commands)

        except Exception as e:
            logger.error(f"Error generating import command for DHCP options: {str(e)}")
            return None
