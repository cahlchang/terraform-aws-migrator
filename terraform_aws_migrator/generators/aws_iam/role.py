# terraform_aws_migrator/generators/aws_iam/role.py

from typing import Dict, Any, Optional
import json
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMRoleGenerator(HCLGenerator):
    """Generator for aws_iam_role resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_role"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            role_name = resource.get("id")
            details = resource.get("details", {})

            # Buffer to store all HCL blocks
            hcl_blocks = []

            # Generate main role HCL
            if resource["type"] == "aws_iam_role":
                assume_role_policy = details.get("assume_role_policy", {})
                description = details.get("description", "")
                path = details.get("path", "/")

                role_hcl = [
                    f'resource "aws_iam_role" "{role_name}" {{',
                    f'  name = "{role_name}"',
                ]

                if description:
                    role_hcl.append(f'  description = "{description}"')

                if path != "/":
                    role_hcl.append(f'  path = "{path}"')

                role_hcl.append(
                    f"  assume_role_policy = jsonencode({json.dumps(assume_role_policy, indent=2)})"
                )

                # Add tags if present
                tags = resource.get("tags", [])
                if tags:
                    role_hcl.append("  tags = {")
                    for tag in tags:
                        key = tag.get("Key", "").replace('"', '\\"')
                        value = tag.get("Value", "").replace('"', '\\"')
                        role_hcl.append(f'    "{key}" = "{value}"')
                    role_hcl.append("  }")

                role_hcl.append("}")
                hcl_blocks.append("\n".join(role_hcl))

            return "\n\n".join(hcl_blocks)

        except Exception as e:
            logger.error(f"Error generating HCL for IAM role: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            role_name = resource.get("id")
            if not role_name:
                logger.error("Missing role name for import command generation")
                return None

            return f"terraform import aws_iam_role.{role_name} {role_name}"

        except Exception as e:
            logger.error(f"Error generating import command for IAM role: {str(e)}")
            return None
