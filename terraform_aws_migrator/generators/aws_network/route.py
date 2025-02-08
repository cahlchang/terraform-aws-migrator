from typing import Dict, Any, Optional
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@register_generator
class RouteGenerator(HCLGenerator):
    """Generator for aws_route resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_route"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from route details"""
        route_id = resource.get("id", "")
        return f"route_{route_id.lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            # Skip if resource is managed
            if resource.get("managed", False):
                logger.debug(f"Skipping managed route resource: {resource.get('id')}")
                return None

            details = resource.get("details", {})
            if not details:
                logger.error("Missing required Route details")
                return None

            resource_name = self._generate_resource_name(resource)
            route_table_id = details.get("route_table_id")

            if not route_table_id:
                logger.error("Missing required route_table_id")
                return None

            hcl_blocks = []

            # Generate aws_route resource
            route_hcl = [
                f'resource "aws_route" "{resource_name}" {{',
                f'  route_table_id = "{route_table_id}"'
            ]

            # Add destination (one of these must be specified)
            if cidr := details.get("destination_cidr_block"):
                route_hcl.append(f'  destination_cidr_block = "{cidr}"')
                logger.debug(f"Added CIDR destination: {cidr}")
            elif ipv6_cidr := details.get("destination_ipv6_cidr_block"):
                route_hcl.append(f'  destination_ipv6_cidr_block = "{ipv6_cidr}"')
                logger.debug(f"Added IPv6 CIDR destination: {ipv6_cidr}")
            elif prefix_list_id := details.get("destination_prefix_list_id"):
                route_hcl.append(f'  destination_prefix_list_id = "{prefix_list_id}"')
                logger.debug(f"Added Prefix List destination: {prefix_list_id}")
            else:
                logger.error(f"Missing destination for route in {route_table_id}")
                return None

            # Handle gateway types
            if vpc_endpoint_id := details.get("vpc_endpoint_id"):
                if details.get("is_vpc_endpoint_association"):
                    # Generate aws_vpc_endpoint_route_table_association resource
                    assoc_name = f"vpce_rtb_assoc_{resource_name}"
                    assoc_hcl = [
                        f'resource "aws_vpc_endpoint_route_table_association" "{assoc_name}" {{',
                        f'  route_table_id = "{route_table_id}"',
                        f'  vpc_endpoint_id = "{vpc_endpoint_id}"',
                        "}"
                    ]
                    hcl_blocks.append("\n".join(assoc_hcl))
                    logger.debug(f"Generated VPC endpoint association HCL for {vpc_endpoint_id}")

            if gateway_id := details.get("gateway_id"):
                logger.debug(f"Using gateway_id: {gateway_id}")
                logger.debug(f"Using gateway_id: {gateway_id}")
                route_hcl.append(f'  gateway_id = "{gateway_id}"')
            elif instance_id := details.get("instance_id"):
                route_hcl.append(f'  instance_id = "{instance_id}"')
            elif nat_gateway_id := details.get("nat_gateway_id"):
                route_hcl.append(f'  nat_gateway_id = "{nat_gateway_id}"')
            elif network_interface_id := details.get("network_interface_id"):
                route_hcl.append(f'  network_interface_id = "{network_interface_id}"')
            elif transit_gateway_id := details.get("transit_gateway_id"):
                route_hcl.append(f'  transit_gateway_id = "{transit_gateway_id}"')
            elif vpc_peering_connection_id := details.get("vpc_peering_connection_id"):
                route_hcl.append(f'  vpc_peering_connection_id = "{vpc_peering_connection_id}"')
            elif carrier_gateway_id := details.get("carrier_gateway_id"):
                route_hcl.append(f'  carrier_gateway_id = "{carrier_gateway_id}"')
            elif egress_only_gateway_id := details.get("egress_only_gateway_id"):
                route_hcl.append(f'  egress_only_gateway_id = "{egress_only_gateway_id}"')
            elif local_gateway_id := details.get("local_gateway_id"):
                route_hcl.append(f'  local_gateway_id = "{local_gateway_id}"')

            # Close route resource block
            route_hcl.append("}")
            hcl_blocks.append("\n".join(route_hcl))

            # Return all HCL blocks
            return "\n\n".join(hcl_blocks)

        except Exception as e:
            logger.error(f"Error generating HCL for Route: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate Terraform import command for the route resource"""
        try:
            import_id = resource.get("import_id")
            if not import_id:
                logger.error("Missing Route import_id for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()
            import_commands = []

            # Generate import command for aws_route
            import_commands.append(
                f"terraform import {prefix + '.' if prefix else ''}aws_route.{resource_name} {import_id}"
            )

            # Generate import command for aws_vpc_endpoint_route_table_association if needed
            details = resource.get("details", {})
            if details.get("is_vpc_endpoint_association"):
                assoc_name = f"vpce_rtb_assoc_{resource_name}"
                route_table_id = details.get("route_table_id")
                vpc_endpoint_id = details.get("vpc_endpoint_id")
                if route_table_id and vpc_endpoint_id:
                    assoc_import_id = f"{vpc_endpoint_id}/{route_table_id}"
                    import_commands.append(
                        f"terraform import {prefix + '.' if prefix else ''}aws_vpc_endpoint_route_table_association.{assoc_name} {assoc_import_id}"
                    )
                    logger.debug(f"Generated VPC endpoint association import command for {vpc_endpoint_id}")

            return "\n".join(import_commands)

        except Exception as e:
            logger.error(f"Error generating import command for Route: {str(e)}")
            return None


@register_generator
class VPCEndpointRouteTableAssociationGenerator(HCLGenerator):
    """Generator for aws_vpc_endpoint_route_table_association resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_vpc_endpoint_route_table_association"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from association details"""
        route_id = resource.get("id", "")
        return f"vpce_rtb_assoc_{route_id.lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            # Skip if resource is managed
            if resource.get("managed", False):
                logger.debug(f"Skipping managed VPC endpoint route table association: {resource.get('id')}")
                return None

            details = resource.get("details", {})
            if not details:
                logger.error("Missing required association details")
                return None

            resource_name = self._generate_resource_name(resource)
            route_table_id = details.get("route_table_id")
            vpc_endpoint_id = details.get("vpc_endpoint_id")

            if not route_table_id or not vpc_endpoint_id:
                logger.error("Missing required route_table_id or vpc_endpoint_id")
                return None

            # Generate HCL
            hcl = [
                f'resource "aws_vpc_endpoint_route_table_association" "{resource_name}" {{',
                f'  route_table_id = "{route_table_id}"',
                f'  vpc_endpoint_id = "{vpc_endpoint_id}"',
                "}"
            ]

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for VPC Endpoint Route Table Association: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate Terraform import command for the association resource"""
        try:
            details = resource.get("details", {})
            route_table_id = details.get("route_table_id")
            vpc_endpoint_id = details.get("vpc_endpoint_id")
            
            if not route_table_id or not vpc_endpoint_id:
                logger.error("Missing required route_table_id or vpc_endpoint_id for import")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()
            import_id = f"{vpc_endpoint_id}/{route_table_id}"
            
            return f"terraform import {prefix + '.' if prefix else ''}aws_vpc_endpoint_route_table_association.{resource_name} {import_id}"

        except Exception as e:
            logger.error(f"Error generating import command: {str(e)}")
            return None
