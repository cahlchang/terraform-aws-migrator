# terraform_aws_migrator/generators/aws_iam/role.py

from typing import Dict, Any, Optional
import json
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class IAMRoleGenerator(HCLGenerator):
    """Generator for aws_iam_role resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_iam_role"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            # Buffer to store all HCL blocks
            hcl_blocks = []
            
            # Generate main role HCL
            if resource["type"] == "aws_iam_role":
                role_name = resource.get("id")
                details = resource.get("details", {})
                
                role_hcl = [
                    f'resource "aws_iam_role" "{role_name}" {{',
                    f'  name = "{role_name}"'
                ]

                if details.get("path"):
                    role_hcl.append(f'  path = "{details["path"]}"')

                assume_role_policy = details.get("assume_role_policy", {})
                role_hcl.append(f"  assume_role_policy = jsonencode({json.dumps(assume_role_policy, indent=2)})")

                tags = resource.get("tags", {})
                if tags:
                    role_hcl.append("  tags = {")
                    for tag in tags:
                        key = tag.get("Key", "").replace('"', '\\"')
                        value = tag.get("Value", "").replace('"', '\\"')
                        role_hcl.append(f'    "{key}" = "{value}"')
                    role_hcl.append("  }")

                role_hcl.append("}")
                hcl_blocks.append("\n".join(role_hcl))

            # Generate inline policy HCL
            elif resource["type"] == "aws_iam_role_policy":
                role_name = resource.get("role_name")
                policy_name = resource.get("policy_name")
                policy_doc = resource.get("policy_document")

                policy_hcl = [
                    f'resource "aws_iam_role_policy" "{role_name}_{policy_name}" {{',
                    f'  name = "{policy_name}"',
                    f'  role = "{role_name}"',
                    f'  policy = jsonencode({json.dumps(policy_doc, indent=2)})',
                    "}"
                ]
                hcl_blocks.append("\n".join(policy_hcl))

            # Generate policy attachment HCL
            elif resource["type"] == "aws_iam_role_policy_attachment":
                role_name = resource.get("role_name")
                policy_arn = resource.get("policy_arn")
                policy_name = policy_arn.split("/")[-1]

                attachment_hcl = [
                    f'resource "aws_iam_role_policy_attachment" "{role_name}_{policy_name}" {{',
                    f'  role       = "{role_name}"',
                    f'  policy_arn = "{policy_arn}"',
                    "}"
                ]
                hcl_blocks.append("\n".join(attachment_hcl))

            return "\n\n".join(hcl_blocks)

        except Exception as e:
            logger.error(f"Error generating HCL for IAM role resources: {str(e)}")
            return None
