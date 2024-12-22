# terraform_aws_migrator/collectors/aws_iam/policy.py

from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


@register_collector
class IAMPolicyCollector(ResourceCollector):
    """Collector for IAM Policies"""

    @classmethod
    def get_service_name(cls) -> str:
        """Return the AWS service name for this collector"""
        return "iam"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        """Return supported resource types and their descriptions"""
        return {
            "aws_iam_policy": "IAM Policies",
        }

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        """
        Collect IAM policy resources.
        
        Args:
            target_resource_type: Optional specific resource type to collect
            
        Returns:
            List of collected IAM policy resources
        """
        if target_resource_type and target_resource_type != "aws_iam_policy":
            return []

        try:
            return self._collect_customer_managed_policies()
        except Exception as e:
            logger.error(f"Error collecting IAM policy resources: {e}")
            return []

    def _collect_customer_managed_policies(self) -> List[Dict[str, Any]]:
        """Collect customer managed IAM policies"""
        resources = []
        paginator = self.client.get_paginator("list_policies")

        try:
            for page in paginator.paginate(Scope="Local"):
                for policy in page["Policies"]:
                    policy_resource = self._process_single_policy(policy)
                    if policy_resource:
                        resources.append(policy_resource)
        except Exception as e:
            logger.error(f"Error during policy collection: {e}")

        return resources

    def _process_single_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single IAM policy and format its data
        
        Args:
            policy: Raw policy data from AWS
            
        Returns:
            Formatted policy resource dictionary
        """
        try:
            policy_arn = policy["Arn"]
            policy_version = self._get_policy_version(policy_arn, policy["DefaultVersionId"])
            tags = self._get_policy_tags(policy_arn)

            return {
                "type": "aws_iam_policy",
                "id": policy["PolicyName"],
                "arn": policy_arn,
                "tags": tags,
                "details": {
                    "description": policy.get("Description", ""),
                    "path": policy["Path"],
                    "policy_document": policy_version["Document"] if policy_version else {},
                    "is_attachable": policy["IsAttachable"],
                    "attachment_count": policy.get("AttachmentCount", 0),
                    "create_date": str(policy["CreateDate"]),
                    "update_date": str(policy["UpdateDate"]),
                },
            }
        except Exception as e:
            logger.error(f"Error processing policy {policy.get('PolicyName', 'Unknown')}: {e}")
            return None

    def _get_policy_version(self, policy_arn: str, version_id: str) -> Dict[str, Any]:
        """Get the specified version of an IAM policy"""
        try:
            return self.client.get_policy_version(
                PolicyArn=policy_arn,
                VersionId=version_id
            )["PolicyVersion"]
        except Exception as e:
            logger.error(f"Error getting policy version for {policy_arn}: {e}")
            return {}

    def _get_policy_tags(self, policy_arn: str) -> List[Dict[str, str]]:
        """Get tags for an IAM policy"""
        try:
            return self.client.list_policy_tags(PolicyArn=policy_arn)["Tags"]
        except Exception:
            return []
