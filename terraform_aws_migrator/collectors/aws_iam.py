from typing import Dict, List, Any
from .base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)

@register_collector
class IAMCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "iam"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_iam_role": "IAM Roles",
            "aws_iam_user": "IAM Users",
            "aws_iam_group": "IAM Groups",
            "aws_iam_policy": "IAM Policies",
            "aws_iam_user_policy": "IAM User Policies",
            "aws_iam_role_policy": "IAM Role Policies",
            "aws_iam_user_policy_attachment": "IAM User Policy Attachments",
            "aws_iam_role_policy_attachment": "IAM Role Policy Attachments",
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        try:
            # Collect existing resources (roles, users, groups)
            resources.extend(self._collect_roles())
            resources.extend(self._collect_users())
            resources.extend(self._collect_groups())

            # Collect policies and attachments
            resources.extend(self._collect_policies())
            resources.extend(self._collect_user_policies())
            resources.extend(self._collect_role_policies())
            resources.extend(self._collect_user_policy_attachments())
            resources.extend(self._collect_role_policy_attachments())

        except Exception as e:
            print(f"Error collecting IAM resources: {str(e)}")

        return resources


    def _collect_roles(self) -> List[Dict[str, Any]]:
        resources = []
        paginator = self.client.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                if not any(rule(role["RoleName"]) for rule in self.get_excluded_rules()):
                    try:
                        tags = self.client.list_role_tags(RoleName=role["RoleName"])["Tags"]
                        # Terraform形式に合わせてIDを生成
                        resource_id = role["Arn"].split("/")[-1]  # パスの最後の部分を使用
                        resources.append({
                            "type": "aws_iam_role",
                            "id": resource_id,
                            "arn": role["Arn"],
                            "tags": tags,
                        })
                        logger.debug(f"Collected IAM role: {resource_id}, ARN: {role['Arn']}")
                    except Exception as e:
                        logger.error(f"Error collecting tags for role {role['RoleName']}: {str(e)}")
        return resources

    def _collect_role_policies(self) -> List[Dict[str, Any]]:
        resources = []
        role_paginator = self.client.get_paginator("list_roles")
        for role_page in role_paginator.paginate():
            for role in role_page["Roles"]:
                if not any(rule(role["RoleName"]) for rule in self.get_excluded_rules()):
                    try:
                        policy_paginator = self.client.get_paginator("list_role_policies")
                        for policy_page in policy_paginator.paginate(RoleName=role["RoleName"]):
                            for policy_name in policy_page["PolicyNames"]:
                                # Terraform形式に合わせてIDを生成
                                resource_id = f"{role['RoleName']}_{policy_name}"  # アンダースコアを使用
                                resources.append({
                                    "type": "aws_iam_role_policy",
                                    "id": resource_id,
                                    "role_name": role["RoleName"],
                                    "policy_name": policy_name
                                })
                                logger.debug(f"Collected IAM role policy: {resource_id}")
                    except Exception as e:
                        logger.error(f"Error collecting inline policies for role {role['RoleName']}: {str(e)}")
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

    def _collect_groups(self) -> List[Dict[str, Any]]:
        """Collect IAM groups"""
        resources = []
        paginator = self.client.get_paginator("list_groups")
        for page in paginator.paginate():
            for group in page["Groups"]:
                resources.append(
                    {"type": "group", "id": group["GroupName"], "arn": group["Arn"]}
                )
        return resources

    def _collect_policies(self) -> List[Dict[str, Any]]:
        """Collect customer managed policies"""
        resources = []
        paginator = self.client.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):  # Only customer managed policies
            for policy in page["Policies"]:
                try:
                    tags = self.client.list_policy_tags(PolicyArn=policy["Arn"])["Tags"]
                    resources.append(
                        {
                            "type": "policy",
                            "id": policy["PolicyName"],
                            "arn": policy["Arn"],
                            "tags": tags,
                        }
                    )
                except Exception as e:
                    print(
                        f"Error collecting tags for policy {policy['PolicyName']}: {str(e)}"
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

    def _collect_role_policy_attachments(self) -> List[Dict[str, Any]]:
        """Collect role policy attachments"""
        resources = []
        role_paginator = self.client.get_paginator("list_roles")
        for role_page in role_paginator.paginate():
            for role in role_page["Roles"]:
                if not any(
                    rule(role["RoleName"]) for rule in self.get_excluded_rules()
                ):
                    try:
                        attachment_paginator = self.client.get_paginator(
                            "list_attached_role_policies"
                        )
                        for attachment_page in attachment_paginator.paginate(
                            RoleName=role["RoleName"]
                        ):
                            for policy in attachment_page["AttachedPolicies"]:
                                resources.append(
                                    {
                                        "type": "role_policy_attachment",
                                        "id": f"{role['RoleName']}:{policy['PolicyName']}",
                                        "role_name": role["RoleName"],
                                        "policy_arn": policy["PolicyArn"],
                                    }
                                )
                    except Exception as e:
                        print(
                            f"Error collecting policy attachments for role {role['RoleName']}: {str(e)}"
                        )
        return resources

    def get_excluded_rules(self) -> List[callable]:
        """Rules for excluding AWS-managed roles"""
        return [
            lambda x: x.startswith("AWSServiceRole"),
            lambda x: x.startswith("aws-service-role"),
            lambda x: x.startswith("OrganizationAccountAccessRole"),
        ]
