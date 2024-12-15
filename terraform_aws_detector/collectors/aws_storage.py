# resource_collectors/storage.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector


@register_collector
class S3Collector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "s3"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_todo": "s3"}

    def collect(self) -> List[Dict[str, Any]]:
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
                        "type": "bucket",
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
        return {"aws_todo": "efs"}

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("describe_file_systems")
            for page in paginator.paginate():
                for fs in page["FileSystems"]:
                    resources.append(
                        {
                            "type": "filesystem",
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
        return "ec2"  # API call is made to EC2 service

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_todo": "ebs"}

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        total_volumes = 0
        managed_volumes = 0

        try:
            paginator = self.client.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page["Volumes"]:
                    total_volumes += 1
                    # Only include volumes that need explicit management
                    if self._should_manage_volume(volume):
                        managed_volumes += 1
                        resources.append(
                            {
                                "type": "volume",
                                "id": volume["VolumeId"],
                                "arn": f"arn:aws:ec2:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:volume/{volume['VolumeId']}",
                                "size": volume["Size"],
                                "tags": volume.get("Tags", []),
                                "attachments": volume.get("Attachments", []),
                                "state": volume.get("State"),
                                "availability_zone": volume.get("AvailabilityZone"),
                                "volume_type": volume.get("VolumeType"),
                            }
                        )

        except Exception as e:
            print(f"Error collecting EBS volumes: {str(e)}")

        return resources

    def _should_manage_volume(self, volume: Dict[str, Any]) -> bool:
        """
        Determine if an EBS volume should be explicitly managed.
        Returns True if:
        - Volume is not attached to any instance
        - Volume has DeleteOnTermination=False for any attachment
        Returns False if:
        - Volume is attached to an instance with DeleteOnTermination=True
        """
        attachments = volume.get("Attachments", [])

        # If volume is not attached, it should be managed
        if not attachments:
            return True

        # Check each attachment
        for attachment in attachments:
            # If DeleteOnTermination is False for any attachment,
            # the volume should be managed explicitly
            if not attachment.get("DeleteOnTermination", True):
                return True

        # Volume is attached and will be deleted with instance(s)
        return False
