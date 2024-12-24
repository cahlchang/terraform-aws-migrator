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
                            "type": "aws_iam_user",
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
                            # Get the policy document
                            try:
                                policy = self.client.get_user_policy(
                                    UserName=user["UserName"], PolicyName=policy_name
                                )
                                resources.append(
                                    {
                                        "type": "aws_iam_user_policy",
                                        "id": f"{user['UserName']}:{policy_name}",
                                        "user_name": user["UserName"],
                                        "policy_name": policy_name,
                                        "policy_document": policy["PolicyDocument"],
                                    }
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error getting policy document for user {user['UserName']}, "
                                    f"policy {policy_name}: {str(e)}"
                                )
                except Exception as e:
                    logger.error(
                        f"Error collecting inline policies for user {user['UserName']}: {str(e)}"
                    )
        return resources

    def _collect_user_policy_attachments(self) -> List[Dict[str, Any]]:
        """Collect user policy attachments"""
        resources = []
        try:
            # list_users with pagination
            user_paginator = self.client.get_paginator("list_users")
            user_page_num = 0
            for user_page in user_paginator.paginate():
                user_page_num += 1
                logger.debug(
                    f"Processing user page {user_page_num} with {len(user_page['Users'])} users"
                )

                for user in user_page["Users"]:
                    user_name = user["UserName"]
                    try:
                        # list_attached_user_policies with pagination
                        attachment_paginator = self.client.get_paginator(
                            "list_attached_user_policies"
                        )
                        policy_page_num = 0
                        total_policies = 0

                        for attachment_page in attachment_paginator.paginate(
                            UserName=user_name,
                            PaginationConfig={"PageSize": 100, "MaxItems": None},
                        ):
                            policy_page_num += 1
                            policies = attachment_page["AttachedPolicies"]
                            total_policies += len(policies)

                            for policy in policies:
                                try:
                                    resources.append(
                                        {
                                            "type": "aws_iam_user_policy_attachment",
                                            "id": f"{user_name}:{policy['PolicyArn']}",
                                            "user_name": user_name,
                                            "policy_arn": policy["PolicyArn"],
                                        }
                                    )
                                except KeyError as ke:
                                    logger.error(
                                        f"Missing required key in policy data for user {user_name}: {ke}"
                                    )
                                    logger.debug(f"Policy data: {policy}")
                                    continue

                        logger.debug(
                            f"User {user_name}: Processed {policy_page_num} pages, found {total_policies} policies"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error collecting policies for user {user_name}: {str(e)}"
                        )
                        logger.debug(f"Full error: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in user policy attachment collection: {str(e)}")
            logger.debug("Full error trace:", exc_info=True)

        logger.info(f"Collected {len(resources)} total user policy attachments")
        return resources

    # return resources
    # def _collect_user_policy_attachments(self) -> List[Dict[str, Any]]:
    #     """Collect user policy attachments"""
    #     resources = []
    #     user_paginator = self.client.get_paginator("list_users")
    #     for user_page in user_paginator.paginate():
    #         for user in user_page["Users"]:
    #             try:
    #                 attachment_paginator = self.client.get_paginator(
    #                     "list_attached_user_policies"
    #                 )
    #                 for attachment_page in attachment_paginator.paginate(
    #                     UserName=user["UserName"]
    #                 ):
    #                     for policy in attachment_page["AttachedPolicies"]:
    #                         resources.append(
    #                             {
    #                                 "type": "aws_iam_user_policy_attachment",
    #                                 "id": f"{user['UserName']}:{policy['PolicyName']}",
    #                                 "user_name": user["UserName"],
    #                                 "policy_arn": policy["PolicyArn"],
    #                             }
    #                         )
    #             except Exception as e:
    #                 print(
    #                     f"Error collecting policy attachments for user {user['UserName']}: {str(e)}"
    #                 )
    #     return resources
