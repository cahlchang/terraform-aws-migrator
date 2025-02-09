from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector

import logging
import json

logger = logging.getLogger(__name__)


@register_collector
class APIGatewayCollector(ResourceCollector):
    @classmethod
    def get_service_name(cls) -> str:
        return "apigateway"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
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
    def get_service_name(cls) -> str:
        return "apigatewayv2"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
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
    def get_service_name(cls) -> str:
        return "route53"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
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
    def get_service_name(cls) -> str:
        return "cloudfront"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        return {"aws_cloudfront_distribution": "CloudFront Distributions"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("list_distributions")
            for page in paginator.paginate():
                for dist in page["DistributionList"].get("Items", []):
                    tags = self.client.list_tags_for_resource(Resource=dist["ARN"])["Tags"]["Items"]

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
    def get_service_name(cls) -> str:
        return "elbv2"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
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

    def is_managed(self, resource: Dict[str, Any]) -> bool:
        """Determine if a resource is managed based on state reader."""
        if not hasattr(self, 'state_reader'):
            return False
        
        managed_resources = self.state_reader.get_managed_resources()
        resource_arn = resource.get("LoadBalancerArn")
        
        if resource_arn in managed_resources:
            return True
        return False

    def generate_resource_identifier(self, resource: Dict[str, Any]) -> str:
        """
        Generate a standardized resource identifier for Load Balancer resources

        Args:
            resource: Dictionary containing resource information
        Returns:
            Unique resource identifier
        """
        resource_type = resource.get("type")
        resource_id = resource.get("id")
        module_path = resource.get("module", "")
        
        # Always use ARN if available
        if "arn" in resource:
            return resource["arn"]
        
        # Generate ARN based on resource type if not available
        if resource_type and resource_id:
            if resource_type == "aws_lb":
                # ALBのARNは loadbalancer/app/{name}/{uuid} の形式
                # tfstateのidはロードバランサーの名前を含む
                return f"arn:aws:elasticloadbalancing:{self.session.region_name}:{self.account_id}:loadbalancer/app/{resource_id}/{resource.get('details', {}).get('uuid', '1234567890')}"
            elif resource_type == "aws_lb_target_group":
                return f"arn:aws:elasticloadbalancing:{self.session.region_name}:{self.account_id}:targetgroup/{resource_id}"
            elif resource_type == "aws_lb_listener":
                lb_arn = resource.get("details", {}).get("load_balancer_arn")
                if lb_arn:
                    return f"{lb_arn}/listener/{resource_id}"
            elif resource_type == "aws_lb_listener_rule":
                listener_arn = resource.get("details", {}).get("listener_arn")
                if listener_arn:
                    return f"{listener_arn}/rule/{resource_id}"
        
        # Fallback to default identifier format
        return f"{resource_type}:{resource_id}" if resource_type and resource_id else resource_id or ""

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        """Collect ALB/NLB resources."""
        resources = []

        try:
            if not target_resource_type or target_resource_type == "aws_lb":
                # Collect load balancers using paginator
                paginator = self.client.get_paginator("describe_load_balancers")
                for page in paginator.paginate():
                    for lb in page["LoadBalancers"]:
                        # Get tags for the load balancer
                        tags_response = self.client.describe_tags(ResourceArns=[lb["LoadBalancerArn"]])
                        tags = tags_response["TagDescriptions"][0]["Tags"] if tags_response["TagDescriptions"] else []

                        # Get managed resource information
                        managed_resources = getattr(self, 'state_reader', {}).get_managed_resources() if hasattr(self, 'state_reader') else {}
                        managed_info = managed_resources.get(lb["LoadBalancerArn"], {})

                        resource = {
                            "type": "aws_lb",
                            "id": lb["LoadBalancerName"],
                            "arn": lb["LoadBalancerArn"],
                            "tags": tags,
                            "managed": bool(managed_info),
                            "details": {
                                "vpc_id": lb.get("VpcId"),
                                "security_groups": lb.get("SecurityGroups", []),
                                "subnets": [az["SubnetId"] for az in lb.get("AvailabilityZones", [])],
                                "dns_name": lb.get("DNSName"),
                                "scheme": lb.get("Scheme"),
                                "load_balancer_type": lb.get("Type")
                            }
                        }

                        # Add module information if available
                        if "module" in managed_info:
                            resource["module"] = managed_info["module"]
                        resources.append(resource)

            if not target_resource_type or target_resource_type == "aws_lb_target_group":
                # Collect target groups using paginator
                paginator = self.client.get_paginator("describe_target_groups")
                for page in paginator.paginate():
                    for tg in page["TargetGroups"]:
                        # Get tags for the target group
                        tags_response = self.client.describe_tags(ResourceArns=[tg["TargetGroupArn"]])
                        tags = tags_response["TagDescriptions"][0]["Tags"] if tags_response["TagDescriptions"] else []

                        # Get target group attributes
                        attributes = self.client.describe_target_group_attributes(
                            TargetGroupArn=tg["TargetGroupArn"]
                        )["Attributes"]

                        resource = {
                            "type": "aws_lb_target_group",
                            "id": tg["TargetGroupName"],
                            "arn": tg["TargetGroupArn"],
                            "tags": tags,
                            "protocol": tg["Protocol"],
                            "port": tg["Port"],
                            "vpc_id": tg["VpcId"],
                            "target_type": tg["TargetType"],
                            "health_check": {
                                "enabled": tg["HealthCheckEnabled"],
                                "path": tg.get("HealthCheckPath"),
                                "protocol": tg["HealthCheckProtocol"],
                                "port": tg["HealthCheckPort"],
                                "interval": tg["HealthCheckIntervalSeconds"],
                                "timeout": tg["HealthCheckTimeoutSeconds"],
                                "healthy_threshold": tg["HealthyThresholdCount"],
                                "unhealthy_threshold": tg["UnhealthyThresholdCount"],
                                "matcher": tg.get("Matcher", {}).get("HttpCode")
                            },
                            "attributes": {attr["Key"]: attr["Value"] for attr in attributes}
                        }
                        resources.append(resource)

        except Exception as e:
            logger.error(f"Error collecting load balancer resources: {e}")

        return resources
