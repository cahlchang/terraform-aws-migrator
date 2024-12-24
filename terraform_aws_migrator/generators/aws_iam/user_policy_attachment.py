# terraform_aws_migrator/generators/aws_iam/user_policy_attachment.py

from typing import Dict, Any, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMUserPolicyAttachmentGenerator(HCLGenerator):
    """Generator for aws_iam_user_policy_attachment resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_user_policy_attachment"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            user_name = resource.get("user_name")
            policy_arn = resource.get("policy_arn")

            if not all([user_name, policy_arn]):
                logger.error(
                    "Missing required fields for user policy attachment generation"
                )
                return None

            # Create unique resource name from user name and policy name
            policy_name = policy_arn.split("/")[-1].replace("-", "_")
            resource_name = f"{user_name}_{policy_name}"

            # Generate HCL
            hcl = [
                f'resource "aws_iam_user_policy_attachment" "{resource_name}" {{',
                f'  user       = "{user_name}"',
                f'  policy_arn = "{policy_arn}"',
                "}",
            ]

            return "\n".join(hcl)

        except Exception as e:
            logger.error(
                f"Error generating HCL for IAM user policy attachment: {str(e)}"
            )
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            user_name = resource.get("user_name")
            policy_arn = resource.get("policy_arn")

            if not all([user_name, policy_arn]):
                logger.error(
                    "Missing required fields for user policy attachment import command"
                )
                return None

            # Create the same resource name used in generate()
            policy_name = policy_arn.split("/")[-1].replace("-", "_")
            resource_name = f"{user_name}_{policy_name}"

            # Import identifier format: username/policy_arn
            import_id = f"{user_name}/{policy_arn}"

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_iam_user_policy_attachment.{resource_name} {import_id}"

        except Exception as e:
            logger.error(
                f"Error generating import command for IAM user policy attachment: {str(e)}"
            )
            return None
