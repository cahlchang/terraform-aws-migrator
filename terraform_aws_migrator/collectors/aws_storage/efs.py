from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


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
