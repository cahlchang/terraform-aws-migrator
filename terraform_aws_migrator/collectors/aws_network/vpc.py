# terraform_aws_migrator/collectors/aws_network/vpc.py

from typing import Dict, List, Any
import logging
import copy
from ..base import ResourceCollector, register_collector

logger = logging.getLogger(__name__)


@register_collector
class VPCCollector(ResourceCollector):
    """Collector for VPC resources"""

    @classmethod
    def get_service_name(cls) -> str:
        return "ec2"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        return {"aws_vpc": "VPC"}

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources: List[Dict[str, Any]] = []
        try:
            if not target_resource_type or target_resource_type == "aws_vpc":
                resources.extend(self._collect_vpcs())
        except Exception as e:
            logger.error(f"Error collecting VPCs: {str(e)}")

        return resources

    def _collect_vpcs(self) -> List[Dict[str, Any]]:
        """Collect VPCs"""
        resources: List[Dict[str, Any]] = []
        try:
            logger.debug("Initializing EC2 client for VPC collection")
            if not self.client:
                logger.error("Failed to initialize EC2 client")
                return resources

            logger.debug("Creating paginator for describe_vpcs")
            paginator = self.client.get_paginator("describe_vpcs")
            for page in paginator.paginate():
                logger.debug(f"Processing VPC page: {page}")
                for vpc in page["Vpcs"]:
                    logger.debug(f"Processing VPC: {vpc}")
                    # Get VPC attributes
                    vpc_attributes = {
                        "enable_dns_support": True,  # デフォルト値
                        "enable_dns_hostnames": False,  # デフォルト値
                    }

                    try:
                        logger.debug(
                            f"Getting DNS support attribute for VPC {vpc['VpcId']}"
                        )
                        dns_support = self.client.describe_vpc_attribute(
                            VpcId=vpc["VpcId"], Attribute="enableDnsSupport"
                        )
                        logger.debug(f"DNS support response: {dns_support}")
                        vpc_attributes["enable_dns_support"] = dns_support[
                            "EnableDnsSupport"
                        ]["Value"]
                    except Exception as e:
                        logger.error(
                            f"Error getting DNS support attribute for VPC {vpc['VpcId']}: {str(e)}"
                        )
                        logger.error(
                            f"Using default value for enable_dns_support: {vpc_attributes['enable_dns_support']}"
                        )

                    try:
                        logger.debug(
                            f"Getting DNS hostnames attribute for VPC {vpc['VpcId']}"
                        )
                        dns_hostnames = self.client.describe_vpc_attribute(
                            VpcId=vpc["VpcId"], Attribute="enableDnsHostnames"
                        )
                        logger.debug(f"DNS hostnames response: {dns_hostnames}")
                        vpc_attributes["enable_dns_hostnames"] = dns_hostnames[
                            "EnableDnsHostnames"
                        ]["Value"]
                    except Exception as e:
                        logger.error(
                            f"Error getting DNS hostnames attribute for VPC {vpc['VpcId']}: {str(e)}"
                        )
                        logger.error(
                            f"Using default value for enable_dns_hostnames: {vpc_attributes['enable_dns_hostnames']}"
                        )

                    try:
                        # Create a deep copy of vpc_attributes to avoid reference issues
                        vpc_details = {
                            "cidr_block": vpc["CidrBlock"],
                            "instance_tenancy": vpc.get("InstanceTenancy", "default"),
                            "enable_dns_support": dict(vpc_attributes).get(
                                "enable_dns_support", True
                            ),
                            "enable_dns_hostnames": dict(vpc_attributes).get(
                                "enable_dns_hostnames", False
                            ),
                            "is_default": vpc.get("IsDefault", False),
                            "cidr_block_associations": [],
                            "ipv6_cidr_block": None,
                            "ipv6_association_id": None,
                            "dhcp_options_id": vpc.get("DhcpOptionsId"),
                            "enable_network_address_usage_metrics": vpc.get(
                                "EnableNetworkAddressUsageMetrics", False
                            ),
                            "enable_classiclink": False,
                            "enable_classiclink_dns_support": False,
                        }

                        # Get Classic Link status
                        try:
                            classic_link_response = self.client.describe_vpc_classic_link(
                                VpcIds=[vpc["VpcId"]]
                            )
                            if classic_link_response["Vpcs"]:
                                vpc_details["enable_classiclink"] = classic_link_response["Vpcs"][0].get(
                                    "ClassicLinkEnabled", False
                                )
                        except Exception as e:
                            logger.error(
                                f"Error getting Classic Link status for VPC {vpc['VpcId']}: {str(e)}"
                            )

                        # Get Classic Link DNS support status
                        try:
                            dns_support_response = self.client.describe_vpc_classic_link_dns_support(
                                VpcIds=[vpc["VpcId"]]
                            )
                            if dns_support_response["Vpcs"]:
                                vpc_details["enable_classiclink_dns_support"] = dns_support_response["Vpcs"][0].get(
                                    "ClassicLinkDnsSupported", False
                                )
                        except Exception as e:
                            logger.error(
                                f"Error getting Classic Link DNS support status for VPC {vpc['VpcId']}: {str(e)}"
                            )
                        logger.debug(f"Building VPC details for {vpc['VpcId']}")

                        # CIDRブロック関連の情報を追加
                        cidr_associations = []
                        for assoc in vpc.get("CidrBlockAssociationSet", []):
                            try:
                                cidr_associations.append(
                                    {
                                        "primary": assoc["CidrBlock"]
                                        == vpc["CidrBlock"],
                                        "cidr_block": assoc["CidrBlock"],
                                        "state": assoc["CidrBlockState"]["State"],
                                    }
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error processing CIDR association for VPC {vpc['VpcId']}: {str(e)}"
                                )
                        vpc_details["cidr_block_associations"] = cidr_associations
                        logger.debug(f"Processed CIDR blocks for VPC {vpc['VpcId']}")

                        # IPv6関連の情報を追加
                        try:
                            ipv6_associations = vpc.get(
                                "Ipv6CidrBlockAssociationSet", []
                            )
                            for assoc in ipv6_associations:
                                if (
                                    assoc.get("Ipv6CidrBlockState", {}).get("State")
                                    == "associated"
                                ):
                                    vpc_details["ipv6_cidr_block"] = assoc.get(
                                        "Ipv6CidrBlock"
                                    )
                                    vpc_details["ipv6_association_id"] = assoc.get(
                                        "AssociationId"
                                    )
                                    break
                            logger.debug(
                                f"Processed IPv6 configuration for VPC {vpc['VpcId']}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error processing IPv6 information for VPC {vpc['VpcId']}: {str(e)}"
                            )

                        logger.debug(
                            f"Final VPC details for {vpc['VpcId']}: {vpc_details}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error creating VPC details for {vpc['VpcId']}: {str(e)}"
                        )
                        continue

                    try:
                        # Create a deep copy of the resource structure
                        logger.debug(
                            f"Creating resource structure for VPC {vpc['VpcId']}"
                        )

                        resource = {
                            "type": "aws_vpc",
                            "id": vpc["VpcId"],
                            "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:vpc/{vpc['VpcId']}",
                            "tags": copy.deepcopy(
                                vpc.get("Tags", [])
                            ),  # Create a deep copy of tags list
                            "details": copy.deepcopy(
                                vpc_details
                            ),  # Create a deep copy of details dictionary
                        }

                        logger.debug(
                            f"Created resource for VPC {vpc['VpcId']} with details"
                        )

                        # Create final copy for appending
                        final_resource = copy.deepcopy(resource)

                        # Verify details are present and not empty
                        if not resource["details"]:
                            logger.error(f"Empty details for VPC {vpc['VpcId']}")
                            continue

                        resources.append(
                            final_resource
                        )  # Add the already deep copied resource
                        logger.debug(f"Added VPC resource: {vpc['VpcId']}")
                    except Exception as e:
                        logger.error(
                            f"Error creating resource for VPC {vpc['VpcId']}: {str(e)}"
                        )
                        continue
        except Exception as e:
            logger.error(f"Error collecting VPCs: {str(e)}")
        return resources


@register_collector
class VPCNetworkComponentsCollector(ResourceCollector):
    """Collector for VPC and related network components"""

    @classmethod
    def get_service_name(cls) -> str:
        return "ec2"

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        return {
            "aws_subnet": "VPC Subnets",
            "aws_route_table": "VPC Route Tables",
            "aws_route": "VPC Routes",
            "aws_internet_gateway": "Internet Gateways",
            "aws_nat_gateway": "NAT Gateways",
            "aws_vpc_endpoint": "VPC Endpoints",
            "aws_network_acl": "Network ACLs",
            "aws_vpc_dhcp_options": "VPC DHCP Options",
        }

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources: List[Dict[str, Any]] = []
        try:
            logger.debug(f"Collecting resources for type: {target_resource_type}")

            # Map resource types to collection methods
            collection_methods = {
                "aws_subnet": self._collect_subnets,
                "aws_route_table": self._collect_route_tables,
                "aws_internet_gateway": self._collect_internet_gateways,
                "aws_nat_gateway": self._collect_nat_gateways,
                "aws_vpc_endpoint": self._collect_vpc_endpoints,
                "aws_network_acl": self._collect_network_acls,
                "aws_vpc_dhcp_options": self._collect_dhcp_options,
            }

            if target_resource_type:
                if target_resource_type in collection_methods:
                    logger.debug(
                        f"Collecting specific resource type: {target_resource_type}"
                    )
                    collected = collection_methods[target_resource_type]()
                    logger.debug(
                        f"Collected {len(collected)} resources of type {target_resource_type}"
                    )
                    resources.extend(collected)
            else:
                # Collect all resource types if no specific type is specified
                for resource_type, collect_method in collection_methods.items():
                    logger.debug(f"Collecting all resources of type: {resource_type}")
                    collected = collect_method()
                    logger.debug(
                        f"Collected {len(collected)} resources of type {resource_type}"
                    )
                    resources.extend(collected)
        except Exception as e:
            logger.error(f"Error collecting VPC components: {str(e)}")

        return resources

    def _collect_subnets(self) -> List[Dict[str, Any]]:
        """Collect VPC Subnets"""
        resources: List[Dict[str, Any]] = []
        try:
            logger.debug("Creating paginator for describe_subnets")
            paginator = self.client.get_paginator("describe_subnets")

            for page in paginator.paginate():
                logger.debug(
                    f"Processing subnet page with {len(page.get('Subnets', []))} subnets"
                )
                for subnet in page["Subnets"]:
                    try:
                        subnet_id = subnet["SubnetId"]
                        logger.debug(f"Processing subnet: {subnet_id}")

                        details = {
                            "vpc_id": subnet["VpcId"],
                            "subnet_id": subnet_id,
                            "cidr_block": subnet["CidrBlock"],
                            "availability_zone": subnet["AvailabilityZone"],
                            "map_public_ip_on_launch": subnet["MapPublicIpOnLaunch"],
                            "assign_ipv6_address_on_creation": subnet.get(
                                "AssignIpv6AddressOnCreation", False
                            ),
                            "ipv6_cidr_block": subnet.get("Ipv6CidrBlock", ""),
                            "enable_dns64": subnet.get("EnableDns64", False),
                        }

                        resource = {
                            "type": "aws_subnet",
                            "id": subnet_id,
                            "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:subnet/{subnet_id}",
                            "tags": subnet.get("Tags", []),
                            "details": details,
                        }

                        resources.append(resource)

                    except KeyError as ke:
                        logger.error(
                            f"Missing required field for subnet {subnet.get('SubnetId', 'unknown')}: {ke}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error processing subnet {subnet.get('SubnetId', 'unknown')}: {str(e)}"
                        )

        except Exception as e:
            logger.error(f"Error collecting subnets: {str(e)}")
            logger.debug(f"Full error details: {str(e)}", exc_info=True)

        logger.debug(f"Collected {len(resources)} subnets in total")
        return resources

    def _collect_route_tables(self) -> List[Dict[str, Any]]:
        """Collect VPC Route Tables and Routes"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_route_tables")
            for page in paginator.paginate():
                for rt in page["RouteTables"]:
                    route_table = {
                        "type": "aws_route_table",
                        "id": rt["RouteTableId"],
                        "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:route-table/{rt['RouteTableId']}",
                        "tags": rt.get("Tags", []),
                        "details": {
                            "vpc_id": rt["VpcId"],
                            "routes": [],
                            "associations": [],
                        },
                    }

                    # Collect routes
                    for route in rt.get("Routes", []):
                        route_detail = {
                            "destination_cidr_block": route.get("DestinationCidrBlock"),
                            "destination_ipv6_cidr_block": route.get(
                                "DestinationIpv6CidrBlock"
                            ),
                            "gateway_id": route.get("GatewayId"),
                            "instance_id": route.get("InstanceId"),
                            "nat_gateway_id": route.get("NatGatewayId"),
                            "network_interface_id": route.get("NetworkInterfaceId"),
                            "vpc_peering_connection_id": route.get(
                                "VpcPeeringConnectionId"
                            ),
                        }
                        route_table["details"]["routes"].append(route_detail)

                    # Collect associations
                    for assoc in rt.get("Associations", []):
                        association = {
                            "id": assoc["RouteTableAssociationId"],
                            "subnet_id": assoc.get("SubnetId"),
                            "gateway_id": assoc.get("GatewayId"),
                            "main": assoc.get("Main", False),
                        }
                        route_table["details"]["associations"].append(association)

                    resources.append(route_table)
        except Exception as e:
            logger.error(f"Error collecting route tables: {str(e)}")
        return resources

    def _collect_internet_gateways(self) -> List[Dict[str, Any]]:
        """Collect Internet Gateways"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_internet_gateways")
            for page in paginator.paginate():
                for igw in page["InternetGateways"]:
                    vpc_attachments = []
                    for attachment in igw.get("Attachments", []):
                        vpc_attachments.append(
                            {
                                "vpc_id": attachment.get("VpcId"),
                                "state": attachment.get("State"),
                            }
                        )

                    resources.append(
                        {
                            "type": "aws_internet_gateway",
                            "id": igw["InternetGatewayId"],
                            "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:internet-gateway/{igw['InternetGatewayId']}",
                            "tags": igw.get("Tags", []),
                            "details": {"vpc_attachments": vpc_attachments},
                        }
                    )
        except Exception as e:
            logger.error(f"Error collecting internet gateways: {str(e)}")
        return resources

    def _collect_nat_gateways(self) -> List[Dict[str, Any]]:
        """Collect NAT Gateways"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_nat_gateways")
            for page in paginator.paginate():
                for nat in page["NatGateways"]:
                    resources.append(
                        {
                            "type": "aws_nat_gateway",
                            "id": nat["NatGatewayId"],
                            "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:nat-gateway/{nat['NatGatewayId']}",
                            "tags": nat.get("Tags", []),
                            "details": {
                                "vpc_id": nat["VpcId"],
                                "subnet_id": nat["SubnetId"],
                                "state": nat["State"],
                                "connectivity_type": nat.get(
                                    "ConnectivityType", "public"
                                ),
                                "elastic_ip_address": nat.get(
                                    "NatGatewayAddresses", [{}]
                                )[0].get("PublicIp"),
                                "private_ip": nat.get("NatGatewayAddresses", [{}])[
                                    0
                                ].get("PrivateIp"),
                                "network_interface_id": nat.get(
                                    "NatGatewayAddresses", [{}]
                                )[0].get("NetworkInterfaceId"),
                            },
                        }
                    )
        except Exception as e:
            logger.error(f"Error collecting NAT gateways: {str(e)}")
        return resources

    def _collect_vpc_endpoints(self) -> List[Dict[str, Any]]:
        """Collect VPC Endpoints"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_vpc_endpoints")
            for page in paginator.paginate():
                for endpoint in page["VpcEndpoints"]:
                    resources.append(
                        {
                            "type": "aws_vpc_endpoint",
                            "id": endpoint["VpcEndpointId"],
                            "arn": endpoint.get("VpcEndpointArn", ""),
                            "tags": endpoint.get("Tags", []),
                            "details": {
                                "vpc_id": endpoint["VpcId"],
                                "service_name": endpoint["ServiceName"],
                                "state": endpoint["State"],
                                "vpc_endpoint_type": endpoint["VpcEndpointType"],
                                "subnet_ids": endpoint.get("SubnetIds", []),
                                "route_table_ids": endpoint.get("RouteTableIds", []),
                                "private_dns_enabled": endpoint.get(
                                    "PrivateDnsEnabled", False
                                ),
                                "network_interface_ids": endpoint.get(
                                    "NetworkInterfaceIds", []
                                ),
                                "dns_entries": endpoint.get("DnsEntries", []),
                                "policy": endpoint.get("PolicyDocument", ""),
                            },
                        }
                    )
        except Exception as e:
            logger.error(f"Error collecting VPC endpoints: {str(e)}")
        return resources

    def _collect_network_acls(self) -> List[Dict[str, Any]]:
        """Collect Network ACLs"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_network_acls")
            for page in paginator.paginate():
                for acl in page["NetworkAcls"]:
                    resources.append(
                        {
                            "type": "aws_network_acl",
                            "id": acl["NetworkAclId"],
                            "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:network-acl/{acl['NetworkAclId']}",
                            "tags": acl.get("Tags", []),
                            "details": {
                                "vpc_id": acl["VpcId"],
                                "is_default": acl["IsDefault"],
                                "ingress_rules": [
                                    rule
                                    for rule in acl.get("Entries", [])
                                    if not rule["Egress"]
                                ],
                                "egress_rules": [
                                    rule
                                    for rule in acl.get("Entries", [])
                                    if rule["Egress"]
                                ],
                                "associations": acl.get("Associations", []),
                            },
                        }
                    )
        except Exception as e:
            logger.error(f"Error collecting network ACLs: {str(e)}")
        return resources

    def _collect_dhcp_options(self) -> List[Dict[str, Any]]:
        """Collect VPC DHCP Options Sets"""
        resources = []
        try:
            paginator = self.client.get_paginator("describe_dhcp_options")
            for page in paginator.paginate():
                for dhcp in page["DhcpOptions"]:
                    resources.append(
                        {
                            "type": "aws_vpc_dhcp_options",
                            "id": dhcp["DhcpOptionsId"],
                            "arn": f"arn:aws:ec2:{self.region}:{self.account_id}:dhcp-options/{dhcp['DhcpOptionsId']}",
                            "tags": dhcp.get("Tags", []),
                            "details": {
                                "domain_name": next(
                                    (
                                        item["Values"]
                                        for item in dhcp["DhcpConfigurations"]
                                        if item["Key"] == "domain-name"
                                    ),
                                    [],
                                ),
                                "domain_name_servers": next(
                                    (
                                        item["Values"]
                                        for item in dhcp["DhcpConfigurations"]
                                        if item["Key"] == "domain-name-servers"
                                    ),
                                    [],
                                ),
                                "ntp_servers": next(
                                    (
                                        item["Values"]
                                        for item in dhcp["DhcpConfigurations"]
                                        if item["Key"] == "ntp-servers"
                                    ),
                                    [],
                                ),
                                "netbios_name_servers": next(
                                    (
                                        item["Values"]
                                        for item in dhcp["DhcpConfigurations"]
                                        if item["Key"] == "netbios-name-servers"
                                    ),
                                    [],
                                ),
                                "netbios_node_type": next(
                                    (
                                        item["Values"]
                                        for item in dhcp["DhcpConfigurations"]
                                        if item["Key"] == "netbios-node-type"
                                    ),
                                    [],
                                ),
                            },
                        }
                    )
        except Exception as e:
            logger.error(f"Error collecting DHCP options: {str(e)}")
        return resources
