from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector

import logging
import traceback
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

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []
        try:
            if target_resource_type:
                if target_resource_type == "aws_iam_role":
                    resources.extend(self._collect_roles())
                elif target_resource_type == "aws_iam_role_policy":
                    resources.extend(self._collect_role_policies())
                elif target_resource_type == "aws_iam_role_policy_attachment":
                    resources.extend(self._collect_role_policy_attachments())
            else:
                resources.extend(self._collect_roles())
                resources.extend(self._collect_role_policies())
                resources.extend(self._collect_role_policy_attachments())
        except Exception as e:
            print(f"Error collecting IAM resources: {traceback.format_exc()}")

        return resources

    def _collect_roles(self) -> List[Dict[str, Any]]:
        resources = []
        paginator = self.client.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                if not any(
                    rule(role["RoleName"]) for rule in self.get_excluded_rules()
                ):
                    try:
                        tags = self.client.list_role_tags(RoleName=role["RoleName"])[
                            "Tags"
                        ]
                        resource_id = role["RoleName"]
                        resources.append(
                            {
                                "type": "aws_iam_role",
                                "id": resource_id,
                                "arn": role["Arn"],
                                "tags": tags,
                                "details": {
                                    "path": role.get("Path"),
                                    "assume_role_policy": role.get(
                                        "AssumeRolePolicyDocument", {}
                                    ),
                                },
                            }
                        )
                    except Exception as e:
                        logger.error(
                            f"Error collecting details for role {role['RoleName']}: {str(e)}"
                        )
        return resources

    def _collect_role_policies(self) -> List[Dict[str, Any]]:
        resources = []
        role_paginator = self.client.get_paginator("list_roles")
        for role_page in role_paginator.paginate():
            for role in role_page["Roles"]:
                if not any(
                    rule(role["RoleName"]) for rule in self.get_excluded_rules()
                ):
                    try:
                        policy_paginator = self.client.get_paginator(
                            "list_role_policies"
                        )
                        for policy_page in policy_paginator.paginate(
                            RoleName=role["RoleName"]
                        ):
                            for policy_name in policy_page["PolicyNames"]:
                                resource_id = f"{role['RoleName']}_{policy_name}"
                                resources.append(
                                    {
                                        "type": "aws_iam_role_policy",
                                        "id": resource_id,
                                        "role_name": role["RoleName"],
                                        "policy_name": policy_name,
                                    }
                                )
                    except Exception as e:
                        logger.error(
                            f"Error collecting inline policies for role {role['RoleName']}: {str(e)}"
                        )
        return resources

    def _collect_role_policy_attachments(self) -> List[Dict[str, Any]]:
        """Collect role policy attachments"""
        resources = []
        role_paginator = self.client.get_paginator("list_roles")
        role_names: List = []
        for role_page in role_paginator.paginate():
            for role in role_page["Roles"]:
                role_names.append(role["RoleName"])

        logger.debug(f"Collecting policy attachments for {len(role_names)} roles")
        # Use STS client to get account ID
        sts_client = self.session.client('sts')
        account_id = sts_client.get_caller_identity()["Account"]
        
        for role_name in role_names:
                if not any(
                    rule(role_name) for rule in self.get_excluded_rules()
                ):
                    try:
                        logger.debug(f"Getting attached policies for role: {role_name}")
                        paginator = self.client.get_paginator("list_attached_role_policies")
                        for page in paginator.paginate(RoleName=role_name):
                            for policy in page["AttachedPolicies"]:
                                attachment = {
                                    "type": "aws_iam_role_policy_attachment",
                                    "id": f"arn:aws:iam::{account_id}:role/{role_name}/{policy['PolicyArn']}",
                                    "role_name": role_name,
                                    "policy_arn": policy["PolicyArn"],
                                }
                                resources.append(attachment)
                                logger.debug(f"Found policy attachment: {attachment['id']}")
                    except Exception as e:
                        logger.error(
                            f"Error collecting policy attachments for role {role_name}: {str(e)}"
                        )

        logger.debug(f"Collected total of {len(resources)} policy attachments")
        return resources

    def get_excluded_rules(self) -> List[callable]:
        """Rules for excluding AWS-managed roles"""
        return [
            lambda x: x.startswith("AWSServiceRole"),
            lambda x: x.startswith("aws-service-role"),
            lambda x: x.startswith("OrganizationAccountAccessRole"),
        ]
