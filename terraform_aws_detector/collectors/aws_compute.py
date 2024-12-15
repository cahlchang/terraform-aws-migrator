# terraform_aws_detector/collectors/aws_compute.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


@register_collector
class EC2Collector(ResourceCollector):
    def get_service_name(self) -> str:
        return "ec2"

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # EC2 instances
            paginator = self.client.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        resources.append(
                            {
                                "type": "instance",
                                "id": instance["InstanceId"],
                                "arn": self.build_arn(
                                    "instance", instance["InstanceId"]
                                ),
                                "tags": instance.get("Tags", []),
                            }
                        )

            # VPCs
            for vpc in self.client.describe_vpcs()["Vpcs"]:
                resources.append(
                    {
                        "type": "vpc",
                        "id": vpc["VpcId"],
                        "arn": self.build_arn("vpc", vpc["VpcId"]),
                        "tags": vpc.get("Tags", []),
                    }
                )

            # Security Groups
            for sg in self.client.describe_security_groups()["SecurityGroups"]:
                resources.append(
                    {
                        "type": "security-group",
                        "id": sg["GroupId"],
                        "arn": self.build_arn("security-group", sg["GroupId"]),
                        "tags": sg.get("Tags", []),
                    }
                )

            # EBS Volumes
            paginator = self.client.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page["Volumes"]:
                    resources.append(
                        {
                            "type": "volume",
                            "id": volume["VolumeId"],
                            "arn": self.build_arn("volume", volume["VolumeId"]),
                            "tags": volume.get("Tags", []),
                        }
                    )

        except Exception as e:
            logger.error(f"Error collecting EC2 resources: {str(e)}")

        return resources


@register_collector
class ECSCollector(ResourceCollector):
    def get_service_name(self) -> str:
        return "ecs"

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # Clusters
            cluster_arns = self.client.list_clusters()["clusterArns"]
            if cluster_arns:
                clusters = self.client.describe_clusters(clusters=cluster_arns)[
                    "clusters"
                ]
                for cluster in clusters:
                    resources.append(
                        {
                            "type": "cluster",
                            "id": cluster["clusterName"],
                            "arn": cluster["clusterArn"],
                            "tags": cluster.get("tags", []),
                        }
                    )

                    # Services in each cluster
                    paginator = self.client.get_paginator("list_services")
                    for page in paginator.paginate(cluster=cluster["clusterName"]):
                        service_arns = page["serviceArns"]
                        if service_arns:
                            services = self.client.describe_services(
                                cluster=cluster["clusterName"], services=service_arns
                            )["services"]
                            for service in services:
                                resources.append(
                                    {
                                        "type": "service",
                                        "id": service["serviceName"],
                                        "arn": service["serviceArn"],
                                        "cluster": cluster["clusterName"],
                                        "tags": service.get("tags", []),
                                    }
                                )

        except Exception as e:
            logger.error(f"Error collecting ECS resources: {str(e)}")

        return resources
