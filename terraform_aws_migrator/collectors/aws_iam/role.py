from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector

import logging

logger = logging.getLogger(__name__)


@register_collector
class IAMRoleCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "iam"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_iam_role": "IAM Roles",
            "aws_iam_role_policy": "IAM Role Policies",
            "aws_iam_role_policy_attachment": "IAM Role Policy Attachments",
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        try:
            resources.extend(self._collect_roles())
            resources.extend(self._collect_role_policies())
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
                        resource_id = role["Arn"].split("/")[-1]
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
