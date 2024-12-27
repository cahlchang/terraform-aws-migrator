# terraform_aws_migrator/collectors/aws_networking.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector

import logging

logger = logging.getLogger(__name__)


@register_collector
class APIGatewayCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "apigateway"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_api_gateway_rest_api": "API Gateway REST APIs"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            # REST APIs
            apis = self.client.get_rest_apis()["items"]
            for api in apis:
                resources.append(
                    {
                        "type": "aws_api_gateway_rest_api",
                        "id": api["id"],
                        "name": api["name"],
                        "arn": f"arn:aws:apigateway:{self.session.region_name}::/restapis/{api['id']}",
                        "tags": api.get("tags", {}),
                    }
                )
        except Exception as e:
            print(f"Error collecting API Gateway resources: {str(e)}")

        return resources


@register_collector
class APIGatewayV2Collector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "apigatewayv2"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_apigatewayv2_api": "API Gateway HTTP/WebSocket APIs"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            # HTTP and WebSocket APIs
            apis = self.client.get_apis()["Items"]
            for api in apis:
                resources.append(
                    {
                        "type": "aws_apigatewayv2_api",
                        "id": api["ApiId"],
                        "name": api["Name"],
                        "arn": f"arn:aws:apigateway:{self.session.region_name}::/apis/{api['ApiId']}",
                        "tags": api.get("Tags", {}),
                    }
                )
        except Exception as e:
            print(f"Error collecting API Gateway V2 resources: {str(e)}")

        return resources


@register_collector
class Route53Collector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "route53"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_route53_zone": "Route 53 Hosted Zones"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            # Hosted zones
            paginator = self.client.get_paginator("list_hosted_zones")
            for page in paginator.paginate():
                for zone in page["HostedZones"]:
                    tags = self.client.list_tags_for_resource(
                        ResourceType="hostedzone",
                        ResourceId=zone["Id"].replace("/hostedzone/", ""),
                    )["ResourceTagSet"]["Tags"]

                    resources.append(
                        {
                            "type": "aws_route53_zone",
                            "id": zone["Id"],
                            "name": zone["Name"],
                            "tags": tags,
                        }
                    )
        except Exception as e:
            print(f"Error collecting Route53 resources: {str(e)}")

        return resources


@register_collector
class CloudFrontCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "cloudfront"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_cloudfront_distribution": "CloudFront Distributions"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("list_distributions")
            for page in paginator.paginate():
                for dist in page["DistributionList"].get("Items", []):
                    tags = self.client.list_tags_for_resource(Resource=dist["ARN"])[
                        "Tags"
                    ]["Items"]

                    resources.append(
                        {
                            "type": "aws_cloudfront_distribution",
                            "id": dist["Id"],
                            "domain_name": dist["DomainName"],
                            "arn": dist["ARN"],
                            "tags": tags,
                        }
                    )
        except Exception as e:
            print(f"Error collecting CloudFront resources: {str(e)}")

        return resources


@register_collector
class LoadBalancerV2Collector(ResourceCollector):
    """Collector for ALB/NLB and related resources (ELBv2)"""

    @classmethod
    def get_service_name(self) -> str:
        return "elbv2"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_lb": "Application and Network Load Balancers",
            "aws_lb_target_group": "Target Groups for ALB/NLB",
            "aws_lb_listener": "Listeners for ALB/NLB",
            "aws_lb_listener_rule": "Routing rules for ALB listeners",
        }

    @classmethod
    def get_resource_service_mappings(cls) -> Dict[str, str]:
        return {
            "aws_lb_target_group": "elbv2",
            "aws_lb": "elbv2",
            "aws_lb_listener": "elbv2",
            "aws_lb_listener_rule": "elbv2",
        }

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            # Collect ALB/NLB
            lb_resources = self._collect_load_balancers()
            resources.extend(lb_resources)

            # Collect Target Groups
            tg_resources = self._collect_target_groups()
            resources.extend(tg_resources)

            # Collect Listeners
            resources.extend(self._collect_listeners())

            # Collect Listener Rules
            resources.extend(self._collect_listener_rules())

            if self.progress_callback:
                self.progress_callback("elbv2", "Completed", len(resources))

        except Exception as e:
            if self.progress_callback:
                self.progress_callback("elbv2", f"Error: {str(e)}", 0)

        return resources

    def _collect_load_balancers(self) -> List[Dict[str, Any]]:
        """Collect ALB and NLB resources"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    # Get tags
                    try:
                        tags_response = self.client.describe_tags(
                            ResourceArns=[lb["LoadBalancerArn"]]
                        )
                        tags = (
                            tags_response["TagDescriptions"][0]["Tags"]
                            if tags_response["TagDescriptions"]
                            else []
                        )
                    except Exception:
                        tags = []

                    resources.append(
                        {
                            "type": "aws_lb",
                            "id": lb["LoadBalancerName"],
                            "arn": lb["LoadBalancerArn"],
                            "tags": tags,
                            "details": {
                                "type": lb["Type"],  # 'application' or 'network'
                                "dns_name": lb.get("DNSName"),
                                "scheme": lb.get("Scheme"),
                                "vpc_id": lb.get("VpcId"),
                                "security_groups": lb.get("SecurityGroups", []),
                                "subnets": [
                                    az["SubnetId"]
                                    for az in lb.get("AvailabilityZones", [])
                                ],
                                "state": lb.get("State", {}).get("Code"),
                                "ip_address_type": lb.get("IpAddressType"),
                            },
                        }
                    )
        except Exception as e:
            print(f"Error collecting load balancers: {e}")
        return resources


    def _collect_target_groups(self) -> List[Dict[str, Any]]:
        """Collect Target Groups and their attachments"""
        resources = []
        try:
            # Collect Target Groups
            paginator = self.client.get_paginator("describe_target_groups")
            for page in paginator.paginate():
                for tg in page["TargetGroups"]:
                    try:
                        # Get tags
                        tags_response = self.client.describe_tags(
                            ResourceArns=[tg["TargetGroupArn"]]
                        )
                        tags = (
                            tags_response["TagDescriptions"][0]["Tags"]
                            if tags_response["TagDescriptions"]
                            else []
                        )
                    except Exception:
                        tags = []

                    # Build health check configuration
                    health_check = None
                    if tg.get("HealthCheckEnabled"):
                        health_check = {
                            "enabled": True,
                            "path": tg.get("HealthCheckPath", "/"),
                            "interval": tg.get("HealthCheckIntervalSeconds"),
                            "timeout": tg.get("HealthCheckTimeoutSeconds"),
                            "healthy_threshold": tg.get("HealthyThresholdCount"),
                            "unhealthy_threshold": tg.get("UnhealthyThresholdCount"),
                            "matcher": tg.get("Matcher", {}).get("HttpCode", "200"),
                        }
                        if tg.get("HealthCheckProtocol"):
                            health_check["protocol"] = tg["HealthCheckProtocol"]
                        if tg.get("HealthCheckPort"):
                            health_check["port"] = tg["HealthCheckPort"]

                    # Build resource details
                    resource = {
                        "type": "aws_lb_target_group",
                        "id": tg["TargetGroupName"],
                        "arn": tg["TargetGroupArn"],
                        "protocol": tg.get("Protocol"),
                        "port": tg.get("Port"),
                        "vpc_id": tg.get("VpcId"),
                        "target_type": tg.get("TargetType"),
                        "tags": tags,
                    }

                    # Add target group attributes
                    try:
                        attrs = self.client.describe_target_group_attributes(
                            TargetGroupArn=tg["TargetGroupArn"]
                        )["Attributes"]

                        for attr in attrs:
                            if attr["Key"] == "deregistration_delay.timeout_seconds":
                                resource["deregistration_delay"] = int(attr["Value"])
                            elif attr["Key"] == "lambda.multi_value_headers.enabled":
                                resource["lambda_multi_value_headers_enabled"] = (
                                    attr["Value"].lower() == "true"
                                )
                            elif attr["Key"] == "proxy_protocol_v2.enabled":
                                resource["proxy_protocol_v2"] = (
                                    attr["Value"].lower() == "true"
                                )
                            elif attr["Key"] == "slow_start.duration_seconds":
                                resource["slow_start"] = int(attr["Value"])
                    except Exception as e:
                        logger.warning(
                            f"Failed to get target group attributes for {tg['TargetGroupName']}: {str(e)}"
                        )

                    # Add health check configuration if any
                    if health_check:
                        resource["health_check"] = health_check

                    resources.append(resource)

        except Exception as e:
            logger.error(f"Error collecting target groups: {str(e)}", exc_info=True)

        return resources


    def _collect_listeners(self) -> List[Dict[str, Any]]:
        """Collect Listeners for ALB/NLB"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    try:
                        listener_paginator = self.client.get_paginator("describe_listeners")
                        for listener_page in listener_paginator.paginate(LoadBalancerArn=lb["LoadBalancerArn"]):
                            for listener in listener_page["Listeners"]:
                                # Get tags
                                try:
                                    tags_response = self.client.describe_tags(
                                        ResourceArns=[listener["ListenerArn"]]
                                    )
                                    tags = (
                                        tags_response["TagDescriptions"][0]["Tags"]
                                        if tags_response["TagDescriptions"]
                                        else []
                                    )
                                except Exception:
                                    tags = []

                                resources.append({
                                    "type": "aws_lb_listener",
                                    "id": listener["ListenerArn"].split("/")[-1],
                                    "arn": listener["ListenerArn"],
                                    "tags": tags,
                                    "details": {
                                        "load_balancer_arn": lb["LoadBalancerArn"],
                                        "port": listener.get("Port"),
                                        "protocol": listener.get("Protocol"),
                                        "ssl_policy": listener.get("SslPolicy"),
                                        "certificates": [
                                            {
                                                "arn": cert.get("CertificateArn"),
                                                "is_default": cert.get("IsDefault", False),
                                            }
                                            for cert in listener.get("Certificates", [])
                                        ],
                                    },
                                })
                    except Exception as e:
                        logger.error(f"Error collecting listeners for LB {lb['LoadBalancerArn']}: {e}")
        except Exception as e:
            logger.error(f"Error collecting listeners: {e}")
        return resources


    def _collect_listener_rules(self) -> List[Dict[str, Any]]:
        """Collect Rules for ALB Listeners"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    try:
                        listener_paginator = self.client.get_paginator("describe_listeners")
                        for listener_page in listener_paginator.paginate(LoadBalancerArn=lb["LoadBalancerArn"]):
                            for listener in listener_page["Listeners"]:
                                try:
                                    rules = self.client.describe_rules(
                                        ListenerArn=listener["ListenerArn"]
                                    ).get("Rules", [])
                                    
                                    for rule in rules:
                                        # Skip default rules
                                        if rule.get("IsDefault", False):
                                            continue
                                            
                                        # Get rule tags
                                        try:
                                            tags_response = self.client.describe_tags(
                                                ResourceArns=[rule["RuleArn"]]
                                            )
                                            tags = (
                                                tags_response["TagDescriptions"][0]["Tags"]
                                                if tags_response["TagDescriptions"]
                                                else []
                                            )
                                        except Exception:
                                            tags = []

                                        resources.append({
                                            "type": "aws_lb_listener_rule",
                                            "id": rule["RuleArn"].split("/")[-1],
                                            "arn": rule["RuleArn"],
                                            "tags": tags,
                                            "details": {
                                                "listener_arn": listener["ListenerArn"],
                                                "priority": rule.get("Priority"),
                                                "conditions": rule.get("Conditions", []),
                                                "actions": rule.get("Actions", []),
                                            },
                                        })
                                except Exception as e:
                                    logger.error(f"Error collecting rules for listener {listener['ListenerArn']}: {e}")
                    except Exception as e:
                        logger.error(f"Error collecting rules for LB {lb['LoadBalancerArn']}: {e}")
        except Exception as e:
            logger.error(f"Error collecting listener rules: {e}")
        return resources

@register_collector
class ClassicLoadBalancerCollector(ResourceCollector):
    """Collector for Classic Load Balancers (ELB)"""

    @classmethod
    def get_service_name(self) -> str:
        return "elb"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {"aws_elb": "Legacy Load Balancers"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []
        try:
            paginator = self.client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancerDescriptions"]:
                    # Get tags
                    try:
                        tags_response = self.client.describe_tags(
                            LoadBalancerNames=[lb["LoadBalancerName"]]
                        )
                        tags = (
                            tags_response["TagDescriptions"][0]["Tags"]
                            if tags_response["TagDescriptions"]
                            else []
                        )
                    except Exception:
                        tags = []

                    resources.append(
                        {
                            "type": "aws_elb",
                            "id": lb["LoadBalancerName"],
                            "arn": f"arn:aws:elasticloadbalancing:{self.session.region_name}:{self.account_id}:loadbalancer/{lb['LoadBalancerName']}",
                            "tags": tags,
                            "details": {
                                "dns_name": lb.get("DNSName"),
                                "scheme": lb.get("Scheme"),
                                "vpc_id": lb.get("VPCId"),
                                "subnets": lb.get("Subnets", []),
                                "security_groups": lb.get("SecurityGroups", []),
                                "instances": [
                                    instance["InstanceId"]
                                    for instance in lb.get("Instances", [])
                                ],
                                "listeners": [
                                    {
                                        "protocol": listener.get("Protocol"),
                                        "load_balancer_port": listener.get(
                                            "LoadBalancerPort"
                                        ),
                                        "instance_protocol": listener.get(
                                            "InstanceProtocol"
                                        ),
                                        "instance_port": listener.get("InstancePort"),
                                        "ssl_certificate_id": listener.get(
                                            "SSLCertificateId"
                                        ),
                                    }
                                    for listener in lb.get("ListenerDescriptions", [])
                                ],
                                "health_check": lb.get("HealthCheck"),
                            },
                        }
                    )

            if self.progress_callback:
                self.progress_callback("elb", "Completed", len(resources))

        except Exception as e:
            if self.progress_callback:
                self.progress_callback("elb", f"Error: {str(e)}", 0)

        return resources
