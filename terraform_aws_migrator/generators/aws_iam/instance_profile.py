# terraform_aws_migrator/generators/aws_iam/instance_profile.py

from typing import Dict, Any, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class IAMInstanceProfileGenerator(HCLGenerator):
    """Generator for aws_iam_instance_profile resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_instance_profile"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for an IAM Instance Profile"""
        try:
            profile_name = resource.get("id")
            details = resource.get("details", {})

            if not profile_name:
                logger.error("Missing required instance profile name")
                return None

            # Start building HCL
            hcl = [
                f'resource "aws_iam_instance_profile" "{profile_name}" {{',
                f'  name = "{profile_name}"'
            ]

            # Add path if not default
            path = details.get("path")
            if path and path != "/":
                hcl.append(f'  path = "{path}"')

            # Add role if present
            role_name = details.get("role_name")
            if role_name:
                hcl.append(f'  role = "{role_name}"')

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
            logger.error(f"Error generating HCL for IAM instance profile: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for IAM Instance Profile"""
        try:
            profile_name = resource.get("id")
            if not profile_name:
                logger.error("Missing instance profile name for import command")
                return None

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_iam_instance_profile.{profile_name} {profile_name}"

        except Exception as e:
            logger.error(f"Error generating import command for IAM instance profile: {str(e)}")
            return None
