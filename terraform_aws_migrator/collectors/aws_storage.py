# resource_collectors/storage.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


@register_collector
class S3Collector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "s3"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_s3_bucket": "S3 Buckets"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            for bucket in self.client.list_buckets()["Buckets"]:
                bucket_name = bucket["Name"]
                try:
                    tags = self.client.get_bucket_tagging(Bucket=bucket_name).get(
                        "TagSet", []
                    )
                except:  # noqa: E722
                    tags = []

                resources.append(
                    {
                        "type": "aws_s3_bucket",
                        "id": bucket_name,
                        "arn": f"arn:aws:s3:::{bucket_name}",
                        "tags": tags,
                    }
                )
        except Exception as e:
            print(f"Error collecting S3 buckets: {str(e)}")

        return resources


@register_collector
class EFSCollector(ResourceCollector):

    @classmethod
    def get_service_name(self) -> str:
        return "efs"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_efs_file_system": "EFS File Systems"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("describe_file_systems")
            for page in paginator.paginate():
                for fs in page["FileSystems"]:
                    resources.append(
                        {
                            "type": "aws_efs_file_system",
                            "id": fs["FileSystemId"],
                            "arn": fs["FileSystemArn"],
                            "tags": fs.get("Tags", []),
                        }
                    )
        except Exception as e:
            print(f"Error collecting EFS filesystems: {str(e)}")

        return resources


@register_collector
class EBSCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "ec2"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_ebs_volume": "EBS Volumes"}

    def _should_manage_volume(self, volume: Dict[str, Any]) -> bool:
        """
        Determine if an EBS volume should be explicitly managed.

        Returns True if:
        - Volume is not attached to any instance (unattached volumes should be managed)
        - Volume has DeleteOnTermination=False for any attachment (preserved volumes should be managed)

        Returns False if:
        - Volume is attached with DeleteOnTermination=True (these are managed with EC2)
        """
        attachments = volume.get("Attachments", [])

        # If volume is not attached, it should be managed
        if not attachments:
            return True

        # Check DeleteOnTermination flag for all attachments
        # If any attachment has DeleteOnTermination=False, the volume should be managed
        for attachment in attachments:
            if not attachment.get("DeleteOnTermination", True):
                return True

        # Volume is attached and all attachments have DeleteOnTermination=True
        return False

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page["Volumes"]:
                    # Only include volumes that should be explicitly managed
                    if not self._should_manage_volume(volume):
                        continue

                    resources.append(
                        {
                            "type": "aws_ebs_volume",
                            "id": volume["VolumeId"],
                            "arn": self.build_arn("volume", volume["VolumeId"]),
                            "tags": volume.get("Tags", []),
                            "details": {
                                "size": volume.get("Size"),
                                "encrypted": volume.get("Encrypted"),
                                "volume_type": volume.get("VolumeType"),
                                "create_time": str(volume.get("CreateTime")),
                                "attachments": [
                                    {
                                        "instance_id": att.get("InstanceId"),
                                        "device": att.get("Device"),
                                        "delete_on_termination": att.get(
                                            "DeleteOnTermination", True
                                        ),
                                    }
                                    for att in volume.get("Attachments", [])
                                ],
                            },
                        }
                    )

        except Exception as e:
            logger.error(f"Error collecting EBS volumes: {str(e)}")

        return resources
