# terraform_aws_migrator/collectors/aws_compute.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


@register_collector
class EC2Collector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "ec2"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_instance": "EC2 Instances",
            "aws_vpc": "Virtual Private Clouds",
            "aws_security_group": "Security Groups",
        }

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

        except Exception as e:
            logger.error(f"Error collecting EC2 resources: {str(e)}")

        return resources


@register_collector
class ECSCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "ecs"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_ecs_cluster": "ECS Clusters", "aws_ecs_service": "ECS Services"}

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


@register_collector
class LambdaCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "lambda"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_lambda_function": "Lambda Functions"}

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        try:
            paginator = self.client.get_paginator("list_functions")
            for page in paginator.paginate():
                for function in page["Functions"]:
                    # Get function tags
                    try:
                        tags = self.client.list_tags(
                            Resource=function["FunctionArn"]
                        ).get("Tags", {})
                    except Exception:
                        tags = {}

                    resources.append(
                        {
                            "type": "aws_lambda_function",
                            "id": function["FunctionName"],
                            "arn": function["FunctionArn"],
                            "tags": tags,
                            "details": {
                                "runtime": function.get("Runtime"),
                                "role": function.get("Role"),
                                "handler": function.get("Handler"),
                                "description": function.get("Description"),
                                "memory_size": function.get("MemorySize"),
                                "timeout": function.get("Timeout"),
                                "last_modified": str(function.get("LastModified")),
                                "version": function.get("Version"),
                            },
                        }
                    )
        except Exception as e:
            print(f"Error collecting Lambda functions: {str(e)}")

        return resources
