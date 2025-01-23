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

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []
        try:
            if not target_resource_type or target_resource_type == "aws_instance":
                resources.extend(self._collect_ec2_instances())

            if not target_resource_type or target_resource_type == "aws_vpc":
                resources.extend(self._collect_vpcs())

            if not target_resource_type or target_resource_type == "aws_security_group":
                resources.extend(self._collect_security_groups())

        except Exception as e:
            logger.error(f"Error collecting EC2 resources: {str(e)}")

        return resources

    def _collect_ec2_instances(self) -> List[Dict[str, Any]]:
        """Collect EC2 instance resources"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        instance_details = {
                            "type": "aws_instance",
                            "id": instance["InstanceId"],
                            "arn": self.build_arn("instance", instance["InstanceId"]),
                            "tags": instance.get("Tags", []),
                            "details": {
                                "instance_type": instance.get("InstanceType"),
                                "ami": instance.get("ImageId"),
                                "availability_zone": instance.get("Placement", {}).get(
                                    "AvailabilityZone"
                                ),
                                "subnet_id": instance.get("SubnetId"),
                                "vpc_id": instance.get("VpcId"),
                                "key_name": instance.get("KeyName"),
                                "vpc_security_group_ids": [
                                    sg["GroupId"]
                                    for sg in instance.get("SecurityGroups", [])
                                ],
                                "ebs_optimized": instance.get("EbsOptimized", False),
                                "monitoring": instance.get("Monitoring", {}).get(
                                    "State"
                                )
                                == "enabled",
                            },
                        }

                        # Get block device mapping
                        block_devices = []
                        for device in instance.get("BlockDeviceMappings", []):
                            if "Ebs" in device:
                                block_devices.append(
                                    {
                                        "device_name": device["DeviceName"],
                                        "volume_id": device["Ebs"]["VolumeId"],
                                        "delete_on_termination": device["Ebs"].get(
                                            "DeleteOnTermination", True
                                        ),
                                    }
                                )
                        if block_devices:
                            instance_details["details"]["block_devices"] = block_devices

                        # Get IPs
                        if instance.get("PublicIpAddress"):
                            instance_details["details"]["public_ip"] = instance[
                                "PublicIpAddress"
                            ]
                        if instance.get("PrivateIpAddress"):
                            instance_details["details"]["private_ip"] = instance[
                                "PrivateIpAddress"
                            ]

                        resources.append(instance_details)

            logger.debug(f"Found {len(resources)} EC2 instances")
            return resources

        except Exception as e:
            logger.error(f"Error collecting EC2 instances: {str(e)}")
            return []

    def _collect_vpcs(self) -> List[Dict[str, Any]]:
        """Collect VPC resources"""
        resources = []
        try:
            for vpc in self.client.describe_vpcs()["Vpcs"]:
                resources.append(
                    {
                        "type": "aws_vpc",
                        "id": vpc["VpcId"],
                        "arn": self.build_arn("vpc", vpc["VpcId"]),
                        "tags": vpc.get("Tags", []),
                        "details": {
                            "cidr_block": vpc.get("CidrBlock"),
                            "instance_tenancy": vpc.get("InstanceTenancy"),
                            "enable_dns_support": vpc.get("EnableDnsSupport"),
                            "enable_dns_hostnames": vpc.get("EnableDnsHostnames"),
                            "is_default": vpc.get("IsDefault", False),
                        },
                    }
                )

            logger.debug(f"Found {len(resources)} VPCs")
            return resources

        except Exception as e:
            logger.error(f"Error collecting VPCs: {str(e)}")
            return []

    def _collect_security_groups(self) -> List[Dict[str, Any]]:
        """Collect security group resources"""
        resources = []
        try:
            for sg in self.client.describe_security_groups()["SecurityGroups"]:
                resources.append(
                    {
                        "type": "aws_security_group",
                        "id": sg["GroupId"],
                        "arn": self.build_arn("security-group", sg["GroupId"]),
                        "tags": sg.get("Tags", []),
                        "details": {
                            "name": sg["GroupName"],
                            "description": sg.get("Description", ""),
                            "vpc_id": sg.get("VpcId"),
                            "revoke_rules_on_delete": False, #default value
                            "ingress_rules": [
                                {
                                    "from_port": rule.get("FromPort"),
                                    "to_port": rule.get("ToPort"),
                                    "protocol": rule.get("IpProtocol"),
                                    "cidr_blocks": [
                                        ip_range["CidrIp"]
                                        for ip_range in rule.get("IpRanges", [])
                                    ],
                                    "ipv6_cidr_blocks": [
                                        ip_range["CidrIpv6"]
                                        for ip_range in rule.get("Ipv6Ranges", [])
                                    ],
                                    "security_groups": [
                                        sg_ref["GroupId"]
                                        for sg_ref in rule.get("UserIdGroupPairs", [])
                                    ],
                                }
                                for rule in sg.get("IpPermissions", [])
                            ],
                            "egress_rules": [
                                {
                                    "from_port": rule.get("FromPort"),
                                    "to_port": rule.get("ToPort"),
                                    "protocol": rule.get("IpProtocol"),
                                    "cidr_blocks": [
                                        ip_range["CidrIp"]
                                        for ip_range in rule.get("IpRanges", [])
                                    ],
                                    "ipv6_cidr_blocks": [
                                        ip_range["CidrIpv6"]
                                        for ip_range in rule.get("Ipv6Ranges", [])
                                    ],
                                    "security_groups": [
                                        sg_ref["GroupId"]
                                        for sg_ref in rule.get("UserIdGroupPairs", [])
                                    ],
                                }
                                for rule in sg.get("IpPermissionsEgress", [])
                            ],
                        },
                    }
                )

            logger.debug(f"Found {len(resources)} security groups")
            return resources

        except Exception as e:
            logger.error(f"Error collecting security groups: {str(e)}")
            return []


@register_collector
class ECSCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "ecs"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_ecs_cluster": "ECS Clusters", "aws_ecs_service": "ECS Services"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
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

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
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

                    details = {
                        "runtime": function.get("Runtime"),
                        "role": function.get("Role"),
                        "handler": function.get("Handler"),
                        "description": function.get("Description"),
                        "memory_size": function.get("MemorySize"),
                        "timeout": function.get("Timeout"),
                        "last_modified": str(function.get("LastModified")),
                        "version": function.get("Version"),
                        "package_type": function.get("PackageType"),
                        "publish": function.get("Publish", False),
                    }

                    if function.get("PackageType") == "Image":
                        try:
                            function_detail = self.client.get_function(FunctionName=function["FunctionName"])
                            code = function_detail.get("Code", {})
                            logger.debug(f"Lambda function code info: {code}")
                            details["image_uri"] = code.get("ImageUri")
                            if image_config := function_detail.get("ImageConfigResponse"):
                                logger.debug(f"Lambda function image config: {image_config}")
                        except Exception as e:
                            logger.error(f"Error getting function details: {str(e)}")
                            details["image_config"] = {
                                "command": image_config.get("ImageConfig", {}).get("Command"),
                                "entry_point": image_config.get("ImageConfig", {}).get("EntryPoint"),
                                "working_directory": image_config.get("ImageConfig", {}).get("WorkingDirectory"),
                            }

                    if env_vars := function.get("Environment", {}).get("Variables"):
                        details["environment"] = {"variables": env_vars}

                    if vpc_config := function.get("VpcConfig"):
                        details["vpc_config"] = {
                            "subnet_ids": vpc_config.get("SubnetIds", []),
                            "security_group_ids": vpc_config.get("SecurityGroupIds", []),
                        }

                    if layers := function.get("Layers"):
                        details["layers"] = [layer.get("Arn") for layer in layers]

                    if dlq := function.get("DeadLetterConfig"):
                        details["dead_letter_config"] = {
                            "target_arn": dlq.get("TargetArn")
                        }

                    if tracing := function.get("TracingConfig"):
                        details["tracing_config"] = {
                            "mode": tracing.get("Mode")
                        }

                    if fs_configs := function.get("FileSystemConfigs", []):
                        details["file_system_config"] = [{
                            "arn": fs.get("Arn"),
                            "local_mount_path": fs.get("LocalMountPath")
                        } for fs in fs_configs]

                    resources.append({
                        "type": "aws_lambda_function",
                        "id": function["FunctionName"],
                        "arn": function["FunctionArn"],
                        "tags": tags,
                        "details": details,
                    })
        except Exception as e:
            print(f"Error collecting Lambda functions: {str(e)}")

        return resources
