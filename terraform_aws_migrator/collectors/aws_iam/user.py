
from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector

import logging

logger = logging.getLogger(__name__)

@register_collector
class IAMUserCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "iam"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_iam_user": "IAM Users",
            "aws_iam_user_policy": "IAM User Policies",
            "aws_iam_user_policy_attachment": "IAM User Policy Attachments",
        }

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []
        try:
            if target_resource_type:
                if target_resource_type == "aws_iam_user":
                    resources.extend(self._collect_users())
                elif target_resource_type == "aws_iam_user_policy":
                    resources.extend(self._collect_user_policies())
                elif target_resource_type == "aws_iam_user_policy_attachment":
                    resources.extend(self._collect_user_policy_attachments())
            else:
                resources.extend(self._collect_users())
                resources.extend(self._collect_user_policies())
                resources.extend(self._collect_user_policy_attachments())
        except Exception as e:
            print(f"Error collecting IAM resources: {str(e)}")

        return resources

    def _collect_users(self) -> List[Dict[str, Any]]:
        """Collect IAM users"""
        resources = []
        paginator = self.client.get_paginator("list_users")
        for page in paginator.paginate():
            for user in page["Users"]:
                try:
                    tags = self.client.list_user_tags(UserName=user["UserName"])["Tags"]
                    resources.append(
                        {
                            "type": "user",
                            "id": user["UserName"],
                            "arn": user["Arn"],
                            "tags": tags,
                        }
                    )
                except Exception as e:
                    print(
                        f"Error collecting tags for user {user['UserName']}: {str(e)}"
                    )
        return resources

    def _collect_user_policies(self) -> List[Dict[str, Any]]:
        """Collect inline user policies"""
        resources = []
        user_paginator = self.client.get_paginator("list_users")
        for user_page in user_paginator.paginate():
            for user in user_page["Users"]:
                try:
                    policy_paginator = self.client.get_paginator("list_user_policies")
                    for policy_page in policy_paginator.paginate(
                        UserName=user["UserName"]
                    ):
                        for policy_name in policy_page["PolicyNames"]:
                            resources.append(
                                {
                                    "type": "user_policy",
                                    "id": f"{user['UserName']}:{policy_name}",
                                    "user_name": user["UserName"],
                                    "policy_name": policy_name,
                                }
                            )
                except Exception as e:
                    print(
                        f"Error collecting inline policies for user {user['UserName']}: {str(e)}"
                    )
        return resources

    def _collect_user_policies(self) -> List[Dict[str, Any]]:
        """Collect inline user policies"""
        resources = []
        user_paginator = self.client.get_paginator("list_users")
        for user_page in user_paginator.paginate():
            for user in user_page["Users"]:
                try:
                    policy_paginator = self.client.get_paginator("list_user_policies")
                    for policy_page in policy_paginator.paginate(
                        UserName=user["UserName"]
                    ):
                        for policy_name in policy_page["PolicyNames"]:
                            resources.append(
                                {
                                    "type": "user_policy",
                                    "id": f"{user['UserName']}:{policy_name}",
                                    "user_name": user["UserName"],
                                    "policy_name": policy_name,
                                }
                            )
                except Exception as e:
                    print(
                        f"Error collecting inline policies for user {user['UserName']}: {str(e)}"
                    )
        return resources


    def _collect_user_policy_attachments(self) -> List[Dict[str, Any]]:
        """Collect user policy attachments"""
        resources = []
        user_paginator = self.client.get_paginator("list_users")
        for user_page in user_paginator.paginate():
            for user in user_page["Users"]:
                try:
                    attachment_paginator = self.client.get_paginator(
                        "list_attached_user_policies"
                    )
                    for attachment_page in attachment_paginator.paginate(
                        UserName=user["UserName"]
                    ):
                        for policy in attachment_page["AttachedPolicies"]:
                            resources.append(
                                {
                                    "type": "user_policy_attachment",
                                    "id": f"{user['UserName']}:{policy['PolicyName']}",
                                    "user_name": user["UserName"],
                                    "policy_arn": policy["PolicyArn"],
                                }
                            )
                except Exception as e:
                    print(
                        f"Error collecting policy attachments for user {user['UserName']}: {str(e)}"
                    )
        return resources
