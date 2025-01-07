from typing import Dict, Any, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class LoadBalancerGenerator(HCLGenerator):
    """Generator for aws_lb resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_lb"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for an Application Load Balancer"""
        try:
            lb_name = resource.get("id")
            details = resource.get("details", {})

            if not lb_name:
                logger.error("Missing required load balancer name")
                return None

            # Start building HCL
            hcl = [
                f'resource "aws_lb" "{lb_name}" {{',
                f'  name = "{lb_name}"',
            ]

            # Add load balancer type
            hcl.append('  load_balancer_type = "application"')

            # Add internal/external scheme
            scheme = details.get("scheme")
            if scheme == "internal":
                hcl.append('  internal = true')
            else:
                hcl.append('  internal = false')

            # Add security groups
            security_groups = details.get("security_groups", [])
            if security_groups:
                groups_str = '", "'.join(security_groups)
                hcl.append(f'  security_groups = ["{groups_str}"]')

            # Add subnets
            subnets = details.get("subnets", [])
            if subnets:
                subnets_str = '", "'.join(subnets)
                hcl.append(f'  subnets = ["{subnets_str}"]')

            # Add IP address type
            ip_address_type = details.get("ip_address_type")
            if ip_address_type:
                hcl.append(f'  ip_address_type = "{ip_address_type.lower()}"')

            # Add idle timeout
            idle_timeout = details.get("idle_timeout")
            if isinstance(idle_timeout, (int, str)) and str(idle_timeout).isdigit():
                hcl.append(f'  idle_timeout = {int(idle_timeout)}')

            # Add tags if present
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        key = tag["Key"].replace('"', '\\"')
                        value = tag["Value"].replace('"', '\\"')
                        hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close the resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for Load Balancer: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for Load Balancer"""
        try:
            lb_arn = resource.get("arn")
            lb_name = resource.get("id")

            if not lb_arn or not lb_name:
                logger.error("Missing required ARN or name for Load Balancer import command")
                return None

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_lb.{lb_name} {lb_arn}"

        except Exception as e:
            logger.error(f"Error generating import command for Load Balancer: {str(e)}")
            return None
