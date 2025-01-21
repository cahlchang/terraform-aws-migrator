# terraform_aws_migrator/collectors/aws_iam/instance_profile.py

from typing import Dict, List, Any, Optional, Set
import concurrent.futures
import logging
from ..base import ResourceCollector, register_collector

logger = logging.getLogger(__name__)


@register_collector
class IAMInstanceProfileCollector(ResourceCollector):
    """Collector for IAM Instance Profiles with caching and parallel processing"""

    def __init__(self, session, progress_callback=None):
        super().__init__(session, progress_callback)
        self._role_details_cache = {}
        self._policy_cache = {}
        self._max_workers = 10

    @classmethod
    def get_service_name(cls) -> str:
        return "iam"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        return {"aws_iam_instance_profile": "IAM Instance Profiles"}

    def _is_aws_managed_path(self, path: str) -> bool:
        """Check if the path indicates an AWS managed role/profile"""
        aws_managed_paths = {"/aws-service-role/", "/service-role/", "/aws-reserved/"}
        return any(path.startswith(prefix) for prefix in aws_managed_paths)

    def _is_aws_service_principal(self, assume_role_policy: Dict) -> bool:
        """Check if the assume role policy trusts AWS services"""
        try:
            statements = assume_role_policy.get("Statement", [])
            for statement in statements:
                principal = statement.get("Principal", {})
                service = principal.get("Service")
                if service:
                    if isinstance(service, str):
                        return service.endswith(".amazonaws.com")
                    elif isinstance(service, list):
                        return any(s.endswith(".amazonaws.com") for s in service)
        except Exception as e:
            logger.error(f"Error parsing assume role policy: {e}")
        return False

    def _get_attached_policies(self, role_name: str) -> List[Dict[str, Any]]:
        """Get attached policies for a role with caching"""
        cache_key = f"policies_{role_name}"
        if cache_key in self._policy_cache:
            return self._policy_cache[cache_key]

        try:
            attached_policies = []
            paginator = self.client.get_paginator("list_attached_role_policies")
            for page in paginator.paginate(RoleName=role_name):
                attached_policies.extend(page["AttachedPolicies"])

            self._policy_cache[cache_key] = attached_policies
            return attached_policies
        except Exception as e:
            logger.error(f"Error getting attached policies for role {role_name}: {e}")
            return []

    def _get_role_details(self, role_name: str) -> Dict[str, Any]:
        """Get detailed information about a role with caching"""
        if role_name in self._role_details_cache:
            return self._role_details_cache[role_name]

        try:
            role = self.client.get_role(RoleName=role_name)["Role"]
            attached_policies = self._get_attached_policies(role_name)

            details = {
                "Path": role.get("Path", "/"),
                "AssumeRolePolicyDocument": role.get("AssumeRolePolicyDocument", {}),
                "AttachedPolicies": attached_policies,
            }

            self._role_details_cache[role_name] = details
            return details
        except Exception as e:
            logger.error(f"Error getting role details for {role_name}: {e}")
            return {}

    def _is_aws_quick_setup_role(self, role_name: str) -> bool:
        """Check if this is specifically an SSM Quick Setup role"""
        quick_setup_patterns = ["AmazonSSMRoleForInstancesQuickSetup"]
        return any(role_name.startswith(pattern) for pattern in quick_setup_patterns)

    def _is_aws_service_managed_role(
        self, role_details: Dict[str, Any], role_name: str
    ) -> bool:
        """Determine if a role is managed by an AWS service based on multiple criteria"""
        if not role_details:
            return False

        # Check path - this is a strong indicator
        if self._is_aws_managed_path(role_details.get("Path", "/")):
            logger.debug(f"Role {role_name} has AWS managed path")
            return True

        # Check for SSM Quick Setup role
        if role_name == "AmazonSSMRoleForInstancesQuickSetup":
            logger.debug(f"Role {role_name} is an SSM Quick Setup role")
            return True

        # Check assume role policy for AWS service principals
        assume_role_policy = role_details.get("AssumeRolePolicyDocument", {})
        statements = assume_role_policy.get("Statement", [])

        # Count unique service principals
        service_principals = set()
        for statement in statements:
            principal = statement.get("Principal", {})
            service = principal.get("Service")
            if service:
                if isinstance(service, str):
                    service_principals.add(service)
                elif isinstance(service, list):
                    service_principals.update(service)

        # If only EC2 is trusted, this is likely a user-managed role
        if service_principals == {"ec2.amazonaws.com"}:
            return False

        # Get attached policies
        attached_policies = role_details.get("AttachedPolicies", [])
        if not attached_policies:
            return False

        # Exclude roles that only have SSM core policies
        if (
            len(attached_policies) == 1
            and attached_policies[0]["PolicyName"] == "AmazonSSMManagedInstanceCore"
        ):
            return False

        # Check for AWS service management indicators
        aws_service_keywords = {
            "AWSQuickSetup",
            "AWSSystemsManager",
            "aws-service-role",
            "service-role",
        }

        has_service_keyword = any(
            any(keyword in policy["PolicyName"] for keyword in aws_service_keywords)
            for policy in attached_policies
        )

        return has_service_keyword

    def _process_profile(self, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single instance profile"""
        try:
            if self._should_exclude_profile(profile):
                return None

            profile_name = profile["InstanceProfileName"]

            # Get profile tags
            try:
                tags = self.client.list_instance_profile_tags(
                    InstanceProfileName=profile_name
                ).get("Tags", [])
            except Exception as e:
                logger.warning(f"Failed to get tags for profile {profile_name}: {e}")
                tags = []

            return {
                "type": "aws_iam_instance_profile",
                "id": profile_name,
                "arn": profile["Arn"],
                "tags": tags,
                "details": {
                    "path": profile.get("Path", "/"),
                    "create_date": str(profile.get("CreateDate", "")),
                    "role_name": (
                        profile["Roles"][0]["RoleName"]
                        if profile.get("Roles")
                        else None
                    ),
                },
            }
        except Exception as e:
            logger.error(
                f"Error processing profile {profile.get('InstanceProfileName', 'unknown')}: {e}"
            )
            return None

    def _should_exclude_profile(self, profile: Dict[str, Any]) -> bool:
        """Determine if an instance profile should be excluded based on AWS service management"""
        profile_name = profile["InstanceProfileName"]

        # Special case for SSM Quick Setup profile
        if profile_name == "AmazonSSMRoleForInstancesQuickSetup":
            logger.debug(
                f"Excluding profile {profile_name} as it is an SSM Quick Setup profile"
            )
            return True

        # Check profile path
        if self._is_aws_managed_path(profile.get("Path", "/")):
            logger.debug(f"Excluding profile {profile_name} due to AWS managed path")
            return True

        # Check attached role
        roles = profile.get("Roles", [])
        if roles:
            role_name = roles[0]["RoleName"]
            role_details = self._get_role_details(role_name)

            if self._is_aws_service_managed_role(role_details, role_name):
                logger.debug(
                    f"Excluding profile {profile_name} due to AWS service managed role"
                )
                return True

        # By default, include the profile
        logger.debug(f"Including profile {profile_name} as customer-managed")
        return False

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        """Collect IAM Instance Profile resources with parallel processing"""
        resources = []
        profiles_to_process = []

        try:
            # First, collect all profiles
            paginator = self.client.get_paginator("list_instance_profiles")
            for page in paginator.paginate():
                profiles_to_process.extend(page["InstanceProfiles"])

            # Process profiles in parallel
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self._max_workers
            ) as executor:
                future_to_profile = {
                    executor.submit(self._process_profile, profile): profile
                    for profile in profiles_to_process
                }

                for future in concurrent.futures.as_completed(future_to_profile):
                    profile = future_to_profile[future]
                    try:
                        if result := future.result():
                            resources.append(result)
                    except Exception as e:
                        logger.error(
                            f"Error processing profile {profile.get('InstanceProfileName', 'unknown')}: {e}"
                        )

        except Exception as e:
            logger.error(f"Error collecting IAM instance profile resources: {e}")

        return resources
