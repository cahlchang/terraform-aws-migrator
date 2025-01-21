# terraform_aws_migrator/collectors/aws_iam/instance_profile.py

from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)

@register_collector
class IAMInstanceProfileCollector(ResourceCollector):
    """Collector for IAM Instance Profiles"""

    @classmethod
    def get_service_name(cls) -> str:
        return "iam"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        return {
            "aws_iam_instance_profile": "IAM Instance Profiles"
        }

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        """Collect IAM Instance Profile resources"""
        resources = []

        try:
            paginator = self.client.get_paginator('list_instance_profiles')
            for page in paginator.paginate():
                for profile in page['InstanceProfiles']:
                    try:
                        # Get profile tags
                        tags = self.client.list_instance_profile_tags(
                            InstanceProfileName=profile['InstanceProfileName']
                        ).get('Tags', [])

                        # Create resource object
                        resource = {
                            "type": "aws_iam_instance_profile",
                            "id": profile['InstanceProfileName'],
                            "arn": profile['Arn'],
                            "tags": tags,
                            "details": {
                                "path": profile.get('Path', '/'),
                                "create_date": str(profile.get('CreateDate', '')),
                                "role_name": profile['Roles'][0]['RoleName'] if profile.get('Roles') else None
                            }
                        }
                        resources.append(resource)

                    except Exception as e:
                        logger.error(f"Error collecting details for instance profile {profile['InstanceProfileName']}: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Error collecting IAM instance profile resources: {str(e)}")

        return resources
