# resource_collectors/network.py

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
