# terraform_aws_migrator/generators/aws_iam/user.py

from typing import Dict, Any, Optional, List
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMUserGenerator(HCLGenerator):
    """Generator for aws_iam_user resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_user"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            user_name = resource.get("id")
            details = resource.get("details", {})

            # Start building HCL
            hcl = [
                f'resource "aws_iam_user" "{user_name}" {{',
                f'  name = "{user_name}"',
            ]

            # Add path if not default
            path = details.get("path", "/")
            if path != "/":
                hcl.append(f'  path = "{path}"')

            # Add permissions boundary if present
            permissions_boundary = details.get("permissions_boundary")
            if permissions_boundary:
                hcl.append(f'  permissions_boundary = "{permissions_boundary}"')

            # Add force_destroy if specified
            force_destroy = details.get("force_destroy", False)
            if force_destroy:
                hcl.append("  force_destroy = true")

            # Add tags if present
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    key = tag.get("Key", "").replace('"', '\\"')
                    value = tag.get("Value", "").replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for IAM user: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for IAM user"""
        try:
            user_name = resource.get("id")
            if not user_name:
                logger.error("Missing user name for import command")
                return None

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_iam_user.{user_name} {user_name}"

        except Exception as e:
            logger.error(f"Error generating import command for IAM user: {str(e)}")
            return None
