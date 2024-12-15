# terraform_aws_detector/collectors/aws_networking.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector

@register_collector
class APIGatewayCollector(ResourceCollector):
    def get_service_name(self) -> str:
        return "apigateway"

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # REST APIs
            apis = self.client.get_rest_apis()["items"]
            for api in apis:
                resources.append(
                    {
                        "type": "rest_api",
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
    def get_service_name(self) -> str:
        return "apigatewayv2"

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # HTTP and WebSocket APIs
            apis = self.client.get_apis()["Items"]
            for api in apis:
                resources.append(
                    {
                        "type": f"{api['ProtocolType'].lower()}_api",
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
    def get_service_name(self) -> str:
        return "route53"

    def collect(self) -> List[Dict[str, Any]]:
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
                            "type": "hosted_zone",
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
    def get_service_name(self) -> str:
        return "cloudfront"

    def collect(self) -> List[Dict[str, Any]]:
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
                            "type": "distribution",
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

    def get_service_name(self) -> str:
        return "elbv2"

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # Collect ALB/NLB
            lb_resources = self._collect_load_balancers()
            resources.extend(lb_resources)

            # Collect Target Groups
            tg_resources = self._collect_target_groups()
            resources.extend(tg_resources)

            # Collect Listeners and Rules
            listener_resources = self._collect_listeners_and_rules()
            resources.extend(listener_resources)

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
            paginator = self.client.get_paginator("describe_target_groups")
            for page in paginator.paginate():
                for tg in page["TargetGroups"]:
                    # Get tags
                    try:
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

                    # Get targets (attachments)
                    try:
                        targets_response = self.client.describe_target_health(
                            TargetGroupArn=tg["TargetGroupArn"]
                        )
                        targets = targets_response.get("TargetHealthDescriptions", [])
                    except Exception:
                        targets = []

                    resources.append(
                        {
                            "type": "aws_lb_target_group",
                            "id": tg["TargetGroupName"],
                            "arn": tg["TargetGroupArn"],
                            "tags": tags,
                            "details": {
                                "protocol": tg.get("Protocol"),
                                "port": tg.get("Port"),
                                "vpc_id": tg.get("VpcId"),
                                "target_type": tg.get("TargetType"),
                                "health_check": {
                                    "protocol": tg.get("HealthCheckProtocol"),
                                    "port": tg.get("HealthCheckPort"),
                                    "path": tg.get("HealthCheckPath"),
                                    "interval": tg.get("HealthCheckIntervalSeconds"),
                                    "timeout": tg.get("HealthCheckTimeoutSeconds"),
                                    "healthy_threshold": tg.get(
                                        "HealthyThresholdCount"
                                    ),
                                    "unhealthy_threshold": tg.get(
                                        "UnhealthyThresholdCount"
                                    ),
                                },
                                "targets": [
                                    {
                                        "id": target["Target"]["Id"],
                                        "port": target["Target"].get("Port"),
                                        "health": target.get("TargetHealth", {}).get(
                                            "State"
                                        ),
                                    }
                                    for target in targets
                                ],
                            },
                        }
                    )
        except Exception as e:
            print(f"Error collecting target groups: {e}")
        return resources

    def _collect_listeners_and_rules(self) -> List[Dict[str, Any]]:
        """Collect Listeners, Rules, and Certificates"""
        resources = []
        try:
            # First get all load balancers
            paginator = self.client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    # Get listeners for each load balancer
                    try:
                        listener_paginator = self.client.get_paginator(
                            "describe_listeners"
                        )
                        for listener_page in listener_paginator.paginate(
                            LoadBalancerArn=lb["LoadBalancerArn"]
                        ):
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

                                # Get rules
                                try:
                                    rules = self.client.describe_rules(
                                        ListenerArn=listener["ListenerArn"]
                                    ).get("Rules", [])
                                except Exception:
                                    rules = []

                                resources.append(
                                    {
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
                                                    "is_default": cert.get(
                                                        "IsDefault", False
                                                    ),
                                                }
                                                for cert in listener.get(
                                                    "Certificates", []
                                                )
                                            ],
                                            "rules": [
                                                {
                                                    "arn": rule["RuleArn"],
                                                    "priority": rule.get("Priority"),
                                                    "conditions": rule.get(
                                                        "Conditions", []
                                                    ),
                                                    "actions": rule.get("Actions", []),
                                                }
                                                for rule in rules
                                                if rule.get("IsDefault", False)
                                                is False  # Skip default rules
                                            ],
                                        },
                                    }
                                )
                    except Exception as e:
                        print(
                            f"Error collecting listeners for LB {lb['LoadBalancerArn']}: {e}"
                        )
        except Exception as e:
            print(f"Error collecting listeners and rules: {e}")
        return resources


@register_collector
class ClassicLoadBalancerCollector(ResourceCollector):
    """Collector for Classic Load Balancers (ELB)"""

    def get_service_name(self) -> str:
        return "elb"

    def collect(self) -> List[Dict[str, Any]]:
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
