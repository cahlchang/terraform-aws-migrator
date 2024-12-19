# terraform_aws_migrator/collectors/aws_iam/group.py

from typing import Dict, List, Any
from terraform_aws_migrator.collectors.base import ResourceCollector, register_collector
import logging
from ..base import ResourceCollector, register_collector

logger = logging.getLogger(__name__)

@register_collector
class IAMGroupCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "iam"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_iam_group": "IAM Groups",
            "aws_iam_group_policy": "IAM Group Policies",
            "aws_iam_group_policy_attachment": "IAM Group Policy Attachments",
            "aws_iam_group_membership": "IAM Group Memberships",
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        try:
            # Collect IAM groups
            paginator = self.client.get_paginator("list_groups")
            for page in paginator.paginate():
                for group in page["Groups"]:
                    try:
                        group_name = group["GroupName"]

                        # Get group members
                        members = self.client.get_group(GroupName=group_name)["Users"]

                        # Get attached policies
                        attached_policies = self.client.list_attached_group_policies(
                            GroupName=group_name
                        )["AttachedPolicies"]

                        # Get inline policies
                        inline_policies = self.client.list_group_policies(
                            GroupName=group_name
                        )["PolicyNames"]

                        inline_policy_documents = {}
                        for policy_name in inline_policies:
                            policy = self.client.get_group_policy(
                                GroupName=group_name, PolicyName=policy_name
                            )
                            inline_policy_documents[policy_name] = policy[
                                "PolicyDocument"
                            ]

                        resources.append(
                            {
                                "type": "aws_iam_group",
                                "id": group_name,
                                "arn": group["Arn"],
                                "details": {
                                    "path": group["Path"],
                                    "members": [user["UserName"] for user in members],
                                    "attached_policies": attached_policies,
                                    "inline_policies": inline_policy_documents,
                                },
                            }
                        )
                    except Exception as e:
                        logger.error(
                            f"Error collecting details for group {group['GroupName']}: {str(e)}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Error collecting IAM group resources: {str(e)}")

        return resources
