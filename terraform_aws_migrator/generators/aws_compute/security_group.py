# terraform_aws_migrator/generators/aws_compute/security_group.py

from typing import Dict, List, Any, Optional
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class SecurityGroupGenerator(HCLGenerator):
    """Generator for aws_security_group resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_security_group"

    def _get_name_from_tags(self, tags: List[Dict[str, str]]) -> Optional[str]:
        """Get Name tag value from tags list"""
        for tag in tags:
            if isinstance(tag, dict) and tag.get("Key") == "Name":
                return tag.get("Value")
        return None

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from Name tag or security group ID"""
        sg_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = self._get_name_from_tags(tags)

        if name_tag:
            # Use Name tag value, sanitized for Terraform
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            # Fallback to security group ID
            return sg_id.replace("-", "_").lower()

    def _format_rule(self, rule: Dict[str, Any], rule_type: str) -> List[str]:
        """Format a single security group rule (ingress or egress)"""
        lines = []

        # Start rule block
        lines.append(f"  {rule_type} {{")

        # Add from_port and to_port
        from_port = rule.get("from_port")
        to_port = rule.get("to_port")
        
        # For egress rules, use default values if not specified
        if rule_type == "egress" and (from_port is None or to_port is None):
            from_port = 0
            to_port = 0
            
        lines.append(f"    from_port = {from_port}")
        lines.append(f"    to_port = {to_port}")

        # Add protocol
        protocol = rule.get("protocol")
        if protocol == "-1":
            protocol = "all"
        lines.append(f'    protocol = "{protocol}"')

        # Add CIDR blocks
        cidr_blocks = rule.get("cidr_blocks", [])
        if cidr_blocks:
            cidr_blocks_str = '", "'.join(cidr_blocks)
            lines.append(f'    cidr_blocks = ["{cidr_blocks_str}"]')

        # Add IPv6 CIDR blocks
        ipv6_cidr_blocks = rule.get("ipv6_cidr_blocks", [])
        if ipv6_cidr_blocks:
            ipv6_blocks_str = '", "'.join(ipv6_cidr_blocks)
            lines.append(f'    ipv6_cidr_blocks = ["{ipv6_blocks_str}"]')

        # Add security group references
        security_groups = rule.get("security_groups", [])
        if security_groups:
            sg_str = '", "'.join(security_groups)
            lines.append(f'    security_groups = ["{sg_str}"]')

        # Close rule block
        lines.append("  }")

        return lines

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            sg_id = resource.get("id")
            details = resource.get("details", {})

            if not sg_id or not details:
                logger.error("Missing required security group details")
                return None

            # Generate resource name
            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_security_group" "{resource_name}" {{',
                f'  name                   = "{details.get("name")}"',
                f'  description            = "{details.get("description", "Managed by Terraform")}"',
                f'  revoke_rules_on_delete = {str(details.get("revoke_rules_on_delete", False)).lower()}',
            ]

            # Add VPC ID if present
            vpc_id = details.get("vpc_id")
            if vpc_id:
                hcl.append(f'  vpc_id = "{vpc_id}"')

            # Add ingress rules
            ingress_rules = details.get("ingress_rules", [])
            for rule in ingress_rules:
                hcl.extend(self._format_rule(rule, "ingress"))

            # Add egress rules
            egress_rules = details.get("egress_rules", [])
            for rule in egress_rules:
                hcl.extend(self._format_rule(rule, "egress"))

            # Add tags
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
            logger.error(f"Error generating HCL for security group: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for security group"""
        try:
            sg_id = resource.get("id")
            if not sg_id:
                logger.error("Missing security group ID for import command")
                return None

            # Generate resource name matching the one in generate()
            resource_name = self._generate_resource_name(resource)

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_security_group.{resource_name} {sg_id}"

        except Exception as e:
            logger.error(
                f"Error generating import command for security group: {str(e)}"
            )
            return None
