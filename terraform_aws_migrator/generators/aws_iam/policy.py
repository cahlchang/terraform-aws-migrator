# terraform_aws_migrator/generators/aws_iam/policy.py

from typing import Dict, Any, Optional
import json
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMPolicyGenerator(HCLGenerator):
    """Generator for aws_iam_policy resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_policy"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            policy_name = resource.get("id")
            details = resource.get("details", {})
            policy_document = details.get("policy_document", {})

            if not policy_name or not policy_document:
                logger.error("Missing required fields for IAM policy generation")
                return None

            # Start building HCL
            hcl = [
                f'resource "aws_iam_policy" "{policy_name}" {{',
                f'  name = "{policy_name}"',
            ]

            # Add description if present
            description = details.get("description")
            if description:
                hcl.append(f'  description = "{description}"')

            # Add path if not default
            path = details.get("path", "/")
            if path != "/":
                hcl.append(f'  path = "{path}"')

            # Add policy document
            hcl.append(
                f"  policy = jsonencode({json.dumps(policy_document, indent=2)})"
            )

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
            logger.error(f"Error generating HCL for IAM policy: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate terraform import command for IAM policy"""
        try:
            arn = resource.get("arn")
            policy_name = resource.get("id")

            if not arn or not policy_name:
                logger.error("Missing ARN or policy name for import command generation")
                return None

            prefix = self.get_import_prefix()
            return (
                f"terraform import {prefix + '.' if prefix else ''}"
                f"aws_iam_policy.{policy_name} {arn}"
            )

        except Exception as e:
            logger.error(f"Error generating import command for IAM policy: {str(e)}")
            return None
