# terraform_aws_migrator/generators/aws_network/route_table.py

from typing import Dict, Any, Optional, List
import logging
from ..base import HCLGenerator, register_generator

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
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            return f"rtb_{route_table_id.replace('-', '_').lower()}"

    def _format_route(self, route: Dict[str, Any]) -> List[str]:
        """Format a single route configuration"""
        route_block = ["  route {"]

        # Add destination
        if cidr := route.get("destination_cidr_block"):
            route_block.append(f'    cidr_block = "{cidr}"')
        elif ipv6_cidr := route.get("destination_ipv6_cidr_block"):
            route_block.append(f'    ipv6_cidr_block = "{ipv6_cidr}"')

        # Add target
        if gateway_id := route.get("gateway_id"):
            route_block.append(f'    gateway_id = "{gateway_id}"')
        if instance_id := route.get("instance_id"):
            route_block.append(f'    instance_id = "{instance_id}"')
        if nat_gateway_id := route.get("nat_gateway_id"):
            route_block.append(f'    nat_gateway_id = "{nat_gateway_id}"')
        if network_interface_id := route.get("network_interface_id"):
            route_block.append(f'    network_interface_id = "{network_interface_id}"')
        if vpc_peering_connection_id := route.get("vpc_peering_connection_id"):
            route_block.append(f'    vpc_peering_connection_id = "{vpc_peering_connection_id}"')

        route_block.append("  }")
        return route_block

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            route_table_id = resource.get("id")
            details = resource.get("details", {})

            if not route_table_id or not details:
                logger.error("Missing required route table details")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_route_table" "{resource_name}" {{',
                f'  vpc_id = "{details["vpc_id"]}"'
            ]

            # Add routes
            routes = details.get("routes", [])
            for route in routes:
                # Skip the local route as it's automatically created
                if route.get("gateway_id") == "local":
                    continue
                hcl.extend(self._format_route(route))

            # Add propagating VGWs if present
            if vgws := details.get("propagating_vgws", []):
                vgws_str = '", "'.join(vgws)
                hcl.append(f'  propagating_vgws = ["{vgws_str}"]')

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    key = tag.get("Key", "").replace('"', '\\"')
                    value = tag.get("Value", "").replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close main resource block
            hcl.append("}")

            # Add route table associations
            associations = details.get("associations", [])
            for assoc in associations:
                if not assoc.get("main", False):  # Skip the main route table association
                    assoc_id = assoc["id"]
                    if subnet_id := assoc.get("subnet_id"):
                        hcl.extend([
                            "",
                            f'resource "aws_route_table_association" "{resource_name}_{assoc_id}" {{',
                            f'  subnet_id = "{subnet_id}"',
                            f'  route_table_id = aws_route_table.{resource_name}.id',
                            "}"
                        ])
                    elif gateway_id := assoc.get("gateway_id"):
                        hcl.extend([
                            "",
                            f'resource "aws_route_table_association" "{resource_name}_{assoc_id}" {{',
                            f'  gateway_id = "{gateway_id}"',
                            f'  route_table_id = aws_route_table.{resource_name}.id',
                            "}"
                        ])

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for route table: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            route_table_id = resource.get("id")
            if not route_table_id:
                logger.error("Missing route table ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            commands = []

            # Main route table import
            prefix = self.get_import_prefix()
            commands.append(
                f"terraform import {prefix + '.' if prefix else ''}"
                f"aws_route_table.{resource_name} {route_table_id}"
            )

            # Route table associations import commands
            details = resource.get("details", {})
            associations = details.get("associations", [])
            for assoc in associations:
                if not assoc.get("main", False):
                    assoc_id = assoc["id"]
                    commands.append(
                        f"terraform import {prefix + '.' if prefix else ''}"
                        f"aws_route_table_association.{resource_name}_{assoc_id} {assoc_id}"
                    )

            return "\n".join(commands)

        except Exception as e:
            logger.error(f"Error generating import command for route table: {str(e)}")
            return None
