# resource_collectors/security.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector


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
            "aws_iam_group": "IAM Groups"
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # Roles
            paginator = self.client.get_paginator("list_roles")
            for page in paginator.paginate():
                for role in page["Roles"]:
                    if not any(
                        rule(role["RoleName"]) for rule in self.get_excluded_rules()
                    ):
                        tags = self.client.list_role_tags(RoleName=role["RoleName"])[
                            "Tags"
                        ]
                        resources.append(
                            {
                                "type": "role",
                                "id": role["RoleName"],
                                "arn": role["Arn"],
                                "tags": tags,
                            }
                        )

            # Users
            paginator = self.client.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page["Users"]:
                    tags = self.client.list_user_tags(UserName=user["UserName"])["Tags"]
                    resources.append(
                        {
                            "type": "user",
                            "id": user["UserName"],
                            "arn": user["Arn"],
                            "tags": tags,
                        }
                    )

            # Groups
            paginator = self.client.get_paginator("list_groups")
            for page in paginator.paginate():
                for group in page["Groups"]:
                    resources.append(
                        {"type": "group", "id": group["GroupName"], "arn": group["Arn"]}
                    )

        except Exception as e:
            print(f"Error collecting IAM resources: {str(e)}")

        return resources

    def get_excluded_rules(self) -> List[callable]:
        """Rules for excluding AWS-managed roles"""
        return [
            lambda x: x.startswith("AWSServiceRole"),
            lambda x: x.startswith("aws-service-role"),
            lambda x: x.startswith("OrganizationAccountAccessRole"),
        ]


@register_collector
class KMSCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "kms"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_kms_key": "KMS Customer-Managed Keys"
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("list_keys")
            for page in paginator.paginate():
                for key in page["Keys"]:
                    key_id = key["KeyId"]
                    try:
                        key_info = self.client.describe_key(KeyId=key_id)["KeyMetadata"]
                        if (
                            key_info["KeyManager"] == "CUSTOMER"
                        ):  # Only collect customer-managed keys
                            tags = self.client.list_resource_tags(KeyId=key_id)["Tags"]
                            resources.append(
                                {
                                    "type": "key",
                                    "id": key_id,
                                    "arn": key_info["Arn"],
                                    "tags": tags,
                                }
                            )
                    except self.client.exceptions.NotFoundException:
                        continue
        except Exception as e:
            print(f"Error collecting KMS resources: {str(e)}")

        return resources


@register_collector
class SecretsManagerCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "secretsmanager"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_secretsmanager_secret": "Secrets Manager Secrets"
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("list_secrets")
            for page in paginator.paginate():
                for secret in page["SecretList"]:
                    resources.append(
                        {
                            "type": "secret",
                            "id": secret["Name"],
                            "arn": secret["ARN"],
                            "tags": secret.get("Tags", []),
                        }
                    )
        except Exception as e:
            print(f"Error collecting Secrets Manager resources: {str(e)}")

        return resources
