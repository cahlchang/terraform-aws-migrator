# terraform_aws_migrator/generators/aws_network/target_group.py

from typing import Dict, Any, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class ALBTargetGroupGenerator(HCLGenerator):
    """Generator for aws_lb_target_group resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_lb_target_group"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for target group based on existing resource"""
        try:
            name = resource.get("id")
            if not name:
                return None

            # Start building HCL
            hcl = [
                f'resource "aws_lb_target_group" "{name}" {{',
                f'  name = "{name}"',
            ]

            # Add basic settings
            protocol = resource.get("protocol")
            if protocol:
                hcl.append(f'  protocol = "{protocol}"')

            port = resource.get("port")
            if port:
                hcl.append(f"  port = {port}")

            vpc_id = resource.get("vpc_id")
            if vpc_id:
                hcl.append(f'  vpc_id = "{vpc_id}"')

            target_type = resource.get("target_type")
            if target_type:
                hcl.append(f'  target_type = "{target_type}"')

            # Add health check if enabled
            health_check = resource.get("health_check")
            if health_check:  # health_check exists means it's enabled
                hcl.append("  health_check {")
                for key, value in health_check.items():
                    if value is not None:
                        if isinstance(value, bool):
                            hcl.append(f"    {key} = {str(value).lower()}")
                        elif isinstance(value, (int, float)):
                            hcl.append(f"    {key} = {value}")
                        else:
                            hcl.append(f'    {key} = "{value}"')
                hcl.append("  }")

            # Add target group attributes
            deregistration_delay = resource.get("deregistration_delay")
            if deregistration_delay:
                hcl.append(f"  deregistration_delay = {deregistration_delay}")

            lambda_multi_value_headers = resource.get(
                "lambda_multi_value_headers_enabled", False
            )
            hcl.append(
                f"  lambda_multi_value_headers_enabled = {str(lambda_multi_value_headers).lower()}"
            )

            proxy_protocol_v2 = resource.get("proxy_protocol_v2", False)
            hcl.append(f"  proxy_protocol_v2 = {str(proxy_protocol_v2).lower()}")

            slow_start = resource.get("slow_start", 0)
            hcl.append(f"  slow_start = {slow_start}")

            # Add tags if present
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
            logger.error(f"Error generating HCL for target group: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for target group"""
        try:
            tg_arn = resource.get("arn")
            tg_name = resource.get("id")

            if not tg_arn or not tg_name:
                logger.error("Missing ARN or name for target group import command")
                return None

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_lb_target_group.{tg_name} {tg_arn}"

        except Exception as e:
            logger.error(f"Error generating import command for target group: {str(e)}")
            return None
