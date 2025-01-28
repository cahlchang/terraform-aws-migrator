# terraform_aws_migrator/generators/aws_network/vpc_endpoint.py

from typing import Dict, Any, Optional, List
import json
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class VPCEndpointGenerator(HCLGenerator):
    """Generator for aws_vpc_endpoint resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_vpc_endpoint"

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from tags or ID"""
        endpoint_id = resource.get("id", "")
        tags = resource.get("tags", [])
        name_tag = next((tag["Value"] for tag in tags if tag["Key"] == "Name"), None)

        if name_tag:
            return name_tag.replace("-", "_").replace(" ", "_").lower()
        else:
            # Get service name from endpoint ID and use it in resource name
            service_name = endpoint_id.split(".")[-1] if "." in endpoint_id else "vpce"
            return f"vpce_{service_name}_{endpoint_id[-8:].lower()}"

    def _format_policy(self, policy: Any) -> Optional[str]:
        """Format the endpoint policy as HCL"""
        if not policy:
            return None

        try:
            if isinstance(policy, str):
                policy_json = json.loads(policy)
            else:
                policy_json = policy
            return f'jsonencode({json.dumps(policy_json, indent=2)})'
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to format endpoint policy: {e}")
            return None

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            endpoint_id = resource.get("id")
            details = resource.get("details", {})

            if not endpoint_id or not details:
                logger.error("Missing required VPC endpoint details")
                return None

            resource_name = self._generate_resource_name(resource)

            # Start building HCL
            hcl = [
                f'resource "aws_vpc_endpoint" "{resource_name}" {{',
                f'  vpc_id = "{details["vpc_id"]}"',
                f'  service_name = "{details["service_name"]}"',
                f'  vpc_endpoint_type = "{details["vpc_endpoint_type"]}"'
            ]

            # Add auto_accept if present
            auto_accept = details.get("auto_accept")
            if auto_accept is not None:
                hcl.append(f'  auto_accept = {str(auto_accept).lower()}')

            # Add type-specific configurations
            endpoint_type = details["vpc_endpoint_type"]
            if endpoint_type == "Interface":
                # Add subnet IDs for Interface endpoints
                if subnet_ids := details.get("subnet_ids"):
                    subnet_ids_str = '", "'.join(subnet_ids)
                    hcl.append(f'  subnet_ids = ["{subnet_ids_str}"]')

                # Add security group IDs for Interface endpoints
                if security_group_ids := details.get("security_group_ids"):
                    sg_ids_str = '", "'.join(security_group_ids)
                    hcl.append(f'  security_group_ids = ["{sg_ids_str}"]')

                # Add private DNS settings
                private_dns_enabled = details.get("private_dns_enabled", False)
                hcl.append(f'  private_dns_enabled = {str(private_dns_enabled).lower()}')

            elif endpoint_type == "Gateway":
                # Add route table IDs for Gateway endpoints
                if route_table_ids := details.get("route_table_ids"):
                    rt_ids_str = '", "'.join(route_table_ids)
                    hcl.append(f'  route_table_ids = ["{rt_ids_str}"]')

            # Add policy if present
            if policy := self._format_policy(details.get("policy")):
                hcl.append(f'  policy = {policy}')

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        key = tag["Key"].replace('"', '\\"')
                        value = tag["Value"].replace('"', '\\"')
                        hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Add timeouts if needed
            hcl.extend([
                "  timeouts {",
                "    create = \"10m\"",
                "    update = \"10m\"",
                "    delete = \"10m\"",
                "  }"
            ])

            # Close resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for VPC endpoint: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            endpoint_id = resource.get("id")
            if not endpoint_id:
                logger.error("Missing VPC endpoint ID for import command")
                return None

            resource_name = self._generate_resource_name(resource)
            prefix = self.get_import_prefix()

            return f"terraform import {prefix + '.' if prefix else ''}aws_vpc_endpoint.{resource_name} {endpoint_id}"

        except Exception as e:
            logger.error(f"Error generating import command for VPC endpoint: {str(e)}")
            return None
