# terraform_aws_migrator/generators/iam_role.py

from typing import Dict, Any, Optional, List
import json
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMGroupGenerator(HCLGenerator):
    """Generator for aws_iam_role resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_role"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            role_name = resource.get("id")
            assume_policy = resource.get("details", {}).get("assume_role_policy", "{}")
            description = resource.get("details", {}).get("description", "")
            tags = resource.get("tags", {})

            hcl = [
                f'resource "aws_iam_role" "{role_name}" {{',
                f'  name = "{role_name}"',
            ]

            if description:
                hcl.append(f'  description = "{description}"')

            hcl.append(f"  assume_role_policy = jsonencode({assume_policy})")

            if tags:
                hcl.append("  tags = {")
                for key, value in tags.items():
                    hcl.append(f'    {key} = "{value}"')
                hcl.append("  }")

            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for IAM role: {str(e)}")
            return None
