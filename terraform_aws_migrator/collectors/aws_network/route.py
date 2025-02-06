from typing import Dict, List, Any, Optional
import logging
from ..base import ResourceCollector, register_collector

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@register_collector
class RouteCollector(ResourceCollector):
    """Collector for Route resources"""

    @classmethod
    def get_service_name(cls) -> str:
        return "ec2"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        return {
            "aws_route": "VPC Routes",
            "aws_vpc_endpoint_route_table_association": "VPC Endpoint Route Table Associations"
        }

    def _sanitize_destination(self, destination: str) -> str:
        """Convert destination string to a safe format"""
        return destination.replace('.', '_').replace('/', '_').replace(':', '_')

    def _get_vpc_endpoint_info(self, vpc_endpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get VPC endpoint information with detailed logging"""
        try:
            logger.debug(f"Fetching VPC endpoint info for {vpc_endpoint_id}")
            response = self.client.describe_vpc_endpoints(
                VpcEndpointIds=[vpc_endpoint_id]
            )
            if response["VpcEndpoints"]:
                endpoint = response["VpcEndpoints"][0]
                endpoint_type = endpoint["VpcEndpointType"]
                service_name = endpoint.get("ServiceName", "").split(".")[-1]
                logger.debug(f"VPC endpoint {vpc_endpoint_id} info: type={endpoint_type}, service={service_name}")
                return endpoint
            logger.warning(f"No VPC endpoint found for {vpc_endpoint_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching VPC endpoint info for {vpc_endpoint_id}: {str(e)}")
            return None

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources: List[Dict[str, Any]] = []
        try:
            # Get managed resources from state for both resource types
            managed_resources = {}
            if hasattr(self, 'state_reader') and self.state_reader:
                route_resources = self.state_reader.get_managed_resources("aws_route")
                assoc_resources = self.state_reader.get_managed_resources("aws_vpc_endpoint_route_table_association")
                managed_resources.update(route_resources)
                managed_resources.update(assoc_resources)
                logger.debug(f"Found managed resources: {managed_resources}")
            # Get route tables
            paginator = self.client.get_paginator("describe_route_tables")
            for page in paginator.paginate():
                for rt in page["RouteTables"]:
                    route_table_id = rt["RouteTableId"]
                    vpc_id = rt["VpcId"]
                    logger.debug(f"Processing route table: {route_table_id}")

                    # Process routes
                    for route in rt.get("Routes", []):
                        # Skip local routes (automatically managed by AWS)
                        if route.get("GatewayId") == "local":
                            logger.debug(f"Skipping local route in {route_table_id}")
                            continue

                        # Check destination
                        destination: Optional[str] = None
                        if cidr := route.get("DestinationCidrBlock"):
                            destination = cidr
                            logger.debug(f"Found CIDR destination: {cidr}")
                        elif ipv6_cidr := route.get("DestinationIpv6CidrBlock"):
                            destination = ipv6_cidr
                            logger.debug(f"Found IPv6 CIDR destination: {ipv6_cidr}")
                        elif prefix_list_id := route.get("DestinationPrefixListId"):
                            destination = prefix_list_id
                            logger.debug(f"Found Prefix List destination: {prefix_list_id}")

                        # Skip routes without destination
                        if destination is None:
                            logger.debug(f"Skipping route in {route_table_id} with no destination")
                            continue

                        # Generate resource name ID
                        name_id = f"{route_table_id}_{self._sanitize_destination(destination)}"
                        # Generate import ID
                        import_id = f"{route_table_id}_{destination}"

                        # Create base route details
                        route_details = {
                            "route_table_id": route_table_id,
                            "vpc_id": vpc_id,
                            "destination_cidr_block": route.get("DestinationCidrBlock"),
                            "destination_ipv6_cidr_block": route.get("DestinationIpv6CidrBlock"),
                            "destination_prefix_list_id": route.get("DestinationPrefixListId"),
                            "gateway_id": None,
                            "instance_id": route.get("InstanceId"),
                            "nat_gateway_id": route.get("NatGatewayId"),
                            "network_interface_id": route.get("NetworkInterfaceId"),
                            "transit_gateway_id": route.get("TransitGatewayId"),
                            "vpc_peering_connection_id": route.get("VpcPeeringConnectionId"),
                            "vpc_endpoint_id": None,
                            "carrier_gateway_id": route.get("CarrierGatewayId"),
                            "egress_only_gateway_id": route.get("EgressOnlyInternetGatewayId"),
                            "local_gateway_id": route.get("LocalGatewayId")
                        }

                        # Handle gateway types
                        if gateway_id := route.get("GatewayId"):
                            # For prefix list destinations with VPC endpoint
                            if destination.startswith("pl-") and gateway_id.startswith("vpce-"):
                                logger.debug(f"Found VPC endpoint {gateway_id} with prefix list {destination}")
                                
                                # Create aws_route resource with special flag for VPC endpoint association
                                route_details = {
                                    "route_table_id": route_table_id,
                                    "destination_prefix_list_id": destination,
                                    "vpc_endpoint_id": gateway_id,
                                    "is_vpc_endpoint_association": True  # Special flag
                                }
                                # Create route resource
                                resource_key = f"aws_route:{name_id}"
                                is_managed = resource_key in managed_resources
                                logger.debug(f"Checking if route is managed: {resource_key} -> {is_managed}")
                                
                                resource_arn = f"arn:aws:ec2:{self.region}:{self.account_id}:route/{name_id}"
                                route_resource = {
                                    "type": "aws_route",
                                    "id": name_id,
                                    "import_id": import_id,
                                    "arn": resource_arn,
                                    "tags": rt.get("Tags", []),
                                    "details": route_details,
                                    "managed": is_managed
                                }
                                resources.append(route_resource)
                                logger.debug(f"Created route resource with VPC endpoint: {route_resource}")

                                # Create VPC endpoint association resource
                                assoc_id = f"{route_table_id}_{gateway_id}"
                                assoc_key = f"aws_vpc_endpoint_route_table_association:{assoc_id}"
                                assoc_arn = f"arn:aws:ec2:{self.region}:{self.account_id}:vpc-endpoint-rtb-assoc/{assoc_id}"
                                is_assoc_managed = assoc_key in managed_resources
                                logger.debug(f"Checking if association is managed: {assoc_key} -> {is_assoc_managed}")

                                assoc_resource = {
                                    "type": "aws_vpc_endpoint_route_table_association",
                                    "id": assoc_id,
                                    "import_id": f"{gateway_id}/{route_table_id}",
                                    "arn": assoc_arn,
                                    "tags": rt.get("Tags", []),
                                    "details": {
                                        "route_table_id": route_table_id,
                                        "vpc_endpoint_id": gateway_id
                                    },
                                    "managed": is_assoc_managed
                                }
                                resources.append(assoc_resource)
                                logger.debug(f"Created VPC endpoint association resource: {assoc_resource}")
                            else:
                                logger.debug(f"Using gateway_id: {gateway_id}")
                                route_details["gateway_id"] = gateway_id

                        # Create route resource
                        resource_key = f"aws_route:{name_id}"
                        is_managed = resource_key in managed_resources
                        logger.debug(f"Checking if route is managed: {resource_key} -> {is_managed}")
                        
                        resource_arn = f"arn:aws:ec2:{self.region}:{self.account_id}:route/{name_id}"
                        resource = {
                            "type": "aws_route",
                            "id": name_id,
                            "import_id": import_id,
                            "arn": resource_arn,
                            "tags": rt.get("Tags", []),
                            "details": route_details,
                            "managed": is_managed
                        }
                        resources.append(resource)
                        logger.debug(f"Created route resource: {resource}")

        except Exception as e:
            logger.error(f"Error collecting routes: {str(e)}")

        return resources
