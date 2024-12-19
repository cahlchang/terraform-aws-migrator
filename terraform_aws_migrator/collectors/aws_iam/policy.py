# terraform_aws_migrator/collectors/aws_iam/policy.py

from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


@register_collector
class IAMPolicyCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "iam"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_iam_policy": "IAM Policies",
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        try:
            # Collect customer managed policies
            paginator = self.client.get_paginator("list_policies")

            # Only get customer managed policies (Scope == 'Local')
            for page in paginator.paginate(Scope="Local"):
                for policy in page["Policies"]:
                    try:
                        policy_arn = policy["Arn"]

                        # Get policy version details
                        policy_version = self.client.get_policy_version(
                            PolicyArn=policy_arn, VersionId=policy["DefaultVersionId"]
                        )["PolicyVersion"]

                        # Get policy tags if available
                        try:
                            tags = self.client.list_policy_tags(PolicyArn=policy_arn)[
                                "Tags"
                            ]
                        except Exception:
                            tags = []

                        resources.append(
                            {
                                "type": "aws_iam_policy",
                                "id": policy["PolicyName"],
                                "arn": policy_arn,
                                "tags": tags,
                                "details": {
                                    "description": policy.get("Description", ""),
                                    "path": policy["Path"],
                                    "policy_document": policy_version["Document"],
                                    "is_attachable": policy["IsAttachable"],
                                    "attachment_count": policy.get(
                                        "AttachmentCount", 0
                                    ),
                                    "create_date": str(policy["CreateDate"]),
                                    "update_date": str(policy["UpdateDate"]),
                                },
                            }
                        )
                    except Exception as e:
                        logger.error(
                            f"Error collecting details for policy {policy['PolicyName']}: {str(e)}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Error collecting IAM policy resources: {str(e)}")

        return resources
