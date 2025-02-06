from typing import Dict, Any, Optional
import logging
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class RouteTableGenerator(HCLGenerator):
    """Generator for aws_route_table resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_route_table"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        route_table_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").replace("/", "_").lower()
        else:
            return f"rt_{route_table_id.replace('-', '_').lower()}"

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            route_table_id = resource.get("id")
            details = resource.get("details", {})

            if not route_table_id or not details:
                logger.error(f"Missing required Route Table details for Route Table {route_table_id}")
                return None

            resource_name = self._generate_resource_name(resource)
            vpc_id = details.get("vpc_id")

            # Start building HCL
            hcl = [
                f'resource "aws_route_table" "{resource_name}" {{',
                f'  vpc_id = "{vpc_id}"'
            ]

            # Add routes
            routes = details.get("routes", [])
            for route in routes:
                # Skip the local route as it's automatically created
                if route.get("gateway_id") == "local":
                    continue

                hcl.append("  route {")
                
                # Add destination
                if cidr := route.get("destination_cidr_block"):
                    hcl.append(f'    cidr_block = "{cidr}"')
                elif ipv6_cidr := route.get("destination_ipv6_cidr_block"):
                    hcl.append(f'    ipv6_cidr_block = "{ipv6_cidr}"')

                # Add target
                if gateway_id := route.get("gateway_id"):
                    hcl.append(f'    gateway_id = "{gateway_id}"')
                if instance_id := route.get("instance_id"):
                    hcl.append(f'    instance_id = "{instance_id}"')
                if nat_gateway_id := route.get("nat_gateway_id"):
                    hcl.append(f'    nat_gateway_id = "{nat_gateway_id}"')
                if network_interface_id := route.get("network_interface_id"):
                    hcl.append(f'    network_interface_id = "{network_interface_id}"')
                if transit_gateway_id := route.get("transit_gateway_id"):
                    hcl.append(f'    transit_gateway_id = "{transit_gateway_id}"')
                if vpc_peering_connection_id := route.get("vpc_peering_connection_id"):
                    hcl.append(f'    vpc_peering_connection_id = "{vpc_peering_connection_id}"')
                if vpc_endpoint_id := route.get("vpc_endpoint_id"):
                    hcl.append(f'    vpc_endpoint_id = "{vpc_endpoint_id}"')
                if carrier_gateway_id := route.get("carrier_gateway_id"):
                    hcl.append(f'    carrier_gateway_id = "{carrier_gateway_id}"')
                if egress_only_gateway_id := route.get("egress_only_gateway_id"):
                    hcl.append(f'    egress_only_gateway_id = "{egress_only_gateway_id}"')
                if local_gateway_id := route.get("local_gateway_id"):
                    hcl.append(f'    local_gateway_id = "{local_gateway_id}"')

                hcl.append("  }")

            # Add propagating_vgws if present
            if vgws := details.get("propagating_vgws", []):
                for vgw in vgws:
                    hcl.append(f'  propagating_vgws = ["{vgw}"]')

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    key = tag.get("Key", "").replace('"', '\\"')
                    value = tag.get("Value", "").replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for Route Table: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            route_table_id = resource.get("id")
            if not route_table_id:
                logger.error("Missing Route Table ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()
            
            return f"terraform import {prefix + '.' if prefix else ''}aws_route_table.{resource_name} {route_table_id}"

        except Exception as e:
            logger.error(f"Error generating import command for Route Table: {str(e)}")
            return None
