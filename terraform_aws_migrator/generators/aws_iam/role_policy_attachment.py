# terraform_aws_migrator/generators/aws_iam/role_policy_attachment.py

from typing import Dict, Any, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class IAMRolePolicyAttachmentGenerator(HCLGenerator):
    """Generator for aws_iam_role_policy_attachment resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_role_policy_attachment"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            role_name = resource.get("role_name")
            policy_arn = resource.get("policy_arn")

            if not role_name or not policy_arn:
                logger.error("Missing required fields for role policy attachment")
                return None

            # Create unique resource name
            policy_name = policy_arn.split("/")[-1].replace("-", "_")
            resource_name = f"{role_name}_{policy_name}"

            # Generate HCL
            hcl = [
                f'resource "aws_iam_role_policy_attachment" "{resource_name}" {{',
                f'  role       = "{role_name}"',
                f'  policy_arn = "{policy_arn}"',
                "}",
            ]

            return "\n".join(hcl)

        except Exception as e:
            logger.error(
                f"Error generating HCL for IAM role policy attachment: {str(e)}"
            )
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            role_name = resource.get("role_name")
            policy_arn = resource.get("policy_arn")

            if not role_name or not policy_arn:
                logger.error(
                    "Missing required fields for role policy attachment import command"
                )
                return None

            policy_name = policy_arn.split("/")[-1].replace("-", "_")
            resource_name = f"{role_name}_{policy_name}"

            import_id = f"{role_name}/{policy_arn}"
            prefix = ""
            return f"terraform import {prefix}.aws_iam_role_policy_attachment.{resource_name} {import_id}"

        except Exception as e:
            logger.error(
                f"Error generating import command for IAM role policy attachment: {str(e)}"
            )
            return None
