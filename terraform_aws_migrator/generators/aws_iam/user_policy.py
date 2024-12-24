# terraform_aws_migrator/generators/aws_iam/user_policy.py

from typing import Dict, Any, Optional
import json
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMUserPolicyGenerator(HCLGenerator):
    """Generator for aws_iam_user_policy resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_user_policy"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            user_name = resource.get("user_name")
            policy_name = resource.get("policy_name")
            policy_document = resource.get("policy_document", {})

            if not all([user_name, policy_name, policy_document]):
                logger.error("Missing required fields for user policy generation")
                return None

            # Create unique resource identifier
            resource_id = f"{user_name}_{policy_name}".replace("-", "_")

            # Generate HCL
            hcl = [
                f'resource "aws_iam_user_policy" "{resource_id}" {{',
                f'  name = "{policy_name}"',
                f'  user = "{user_name}"',
                "",
                f"  policy = jsonencode({json.dumps(policy_document, indent=2)})",
                "}",
            ]

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for IAM user policy: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            user_name = resource.get("user_name")
            policy_name = resource.get("policy_name")

            if not all([user_name, policy_name]):
                logger.error("Missing required fields for user policy import command")
                return None

            # Create resource identifier matching the one in generate()
            resource_id = f"{user_name}_{policy_name}".replace("-", "_")

            # Import identifier format: username:policyname
            import_id = f"{user_name}:{policy_name}"

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_iam_user_policy.{resource_id} {import_id}"

        except Exception as e:
            logger.error(
                f"Error generating import command for IAM user policy: {str(e)}"
            )
            return None
