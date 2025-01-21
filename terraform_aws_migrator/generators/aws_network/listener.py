# terraform_aws_migrator/generators/aws_network/listener.py

from typing import Dict, Any, List, Optional
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

class ListenerConfigError(Exception):
    """Exception raised for missing listener configuration"""
    pass

@register_generator
class ALBListenerGenerator(HCLGenerator):
    """Generator for aws_lb_listener resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_lb_listener"

    def _format_certificates(self, certificates: list) -> str:
        """Format SSL certificate configuration block"""
        if not certificates:
            return ""
        
        cert_blocks = []
        for cert in certificates:
            if not cert.get("CertificateArn"):
                continue
            cert_block = [
                "  certificate {",
                f'    certificate_arn = "{cert["CertificateArn"]}"'
            ]
            if cert.get("IsDefault"):
                cert_block.append("    is_default = true")
            cert_block.append("  }")
            cert_blocks.append("\n".join(cert_block))
        
        return "\n".join(cert_blocks)

    def _format_forward_config(self, action: Dict[str, Any]) -> List[str]:
        """Format forward action configuration"""
        config = []
        target_group_arn = None
        
        # Get target group ARN and prepare target groups
        if "TargetGroupArn" in action:
            target_group_arn = action["TargetGroupArn"]
            target_groups = [{
                "TargetGroupArn": target_group_arn,
                "Weight": action.get("Weight", 1)
            }]
        else:
            forward_config = action.get("ForwardConfig", {})
            target_groups = forward_config.get("TargetGroups", [])
            if target_groups and len(target_groups) == 1:
                target_group_arn = target_groups[0]["TargetGroupArn"]

        # Add target_group_arn setting
        if target_group_arn:
            config.append(f'    target_group_arn = "{target_group_arn}"')

        # Add forward block
        lines = ["forward {"]
        
        # Format target groups
        for tg in target_groups:
            target_group_config = [
                "  target_group {",
                f'    arn    = "{tg["TargetGroupArn"]}"'
            ]
            
            # Use weight from the configuration if available
            if "Weight" in tg:
                target_group_config.append(f'    weight = {tg["Weight"]}')
            
            target_group_config.append("  }")
            lines.extend(target_group_config)

        # Add stickiness configuration from actual settings
        stickiness = action.get("ForwardConfig", {}).get("TargetGroupStickinessConfig", {})
        duration_seconds = stickiness.get("DurationSeconds", 1)  # Fallback to 1 if not set
        
        # Stickiness block is always required with both enabled and duration
        lines.extend([
            "  stickiness {",
            f'    enabled  = {str(stickiness.get("Enabled", False)).lower()}',
            f'    duration = {duration_seconds}',
            "  }"
        ])

        lines.append("}")
        config.append("    " + "\n    ".join(lines))
        
        return config

    def _format_fixed_response_config(self, action: Dict[str, Any]) -> List[str]:
        """Format fixed response action configuration"""
        fixed_response_config = action.get("FixedResponseConfig", {})
        if not fixed_response_config:
            return []

        lines = ["    fixed_response {"]
        
        if "ContentType" in fixed_response_config:
            lines.append(f'      content_type = "{fixed_response_config["ContentType"]}"')
        if "MessageBody" in fixed_response_config:
            lines.append(f'      message_body = "{fixed_response_config["MessageBody"]}"')
        if "StatusCode" in fixed_response_config:
            lines.append(f'      status_code  = "{fixed_response_config["StatusCode"]}"')

        lines.append("    }")
        return lines

    def _format_redirect_config(self, action: Dict[str, Any]) -> List[str]:
        """Format redirect action configuration"""
        redirect_config = action.get("RedirectConfig", {})
        if not redirect_config:
            return []

        lines = ["    redirect {"]
        
        param_mapping = {
            "Host": "host",
            "Path": "path",
            "Port": "port",
            "Protocol": "protocol",
            "Query": "query",
            "StatusCode": "status_code"
        }

        for aws_param, tf_param in param_mapping.items():
            if aws_param in redirect_config:
                value = redirect_config[aws_param]
                lines.append(f'      {tf_param} = "{value}"')

        lines.append("    }")
        return lines

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for an ALB listener"""
        try:
            listener_id = resource.get("id")
            details = resource.get("details", {})
            
            if not listener_id or not details:
                raise ListenerConfigError("Missing required listener details")

            # Start building HCL
            hcl = [
                f'resource "aws_lb_listener" "listener_{listener_id}" {{',
                f'  load_balancer_arn = "{details.get("load_balancer_arn")}"',
                f'  port              = {details.get("port", 80)}',
                f'  protocol          = "{details.get("protocol", "HTTP")}"'
            ]

            # Add SSL policy for HTTPS
            if details.get("protocol") == "HTTPS":
                ssl_policy = details.get("ssl_policy")
                if ssl_policy:
                    hcl.append(f'  ssl_policy = "{ssl_policy}"')

                # Add certificate configuration
                certificates = details.get("certificates", [])
                cert_blocks = self._format_certificates(certificates)
                if cert_blocks:
                    hcl.append(cert_blocks)

            # Handle default action
            actions = details.get("actions", [])
            if not actions:
                raise ListenerConfigError(f"No default_action found for listener {listener_id}")

            default_action = actions[0]  # First action is the default action
            action_type = default_action.get("Type", "").lower()
            
            # Add default action block
            hcl.append("  default_action {")
            hcl.append(f'    type = "{action_type}"')
            
            # Format action configuration based on type
            if action_type == "forward":
                config = self._format_forward_config(default_action)
            elif action_type == "fixed-response":
                config = self._format_fixed_response_config(default_action)
            elif action_type == "redirect":
                config = self._format_redirect_config(default_action)
            else:
                config = []

            hcl.extend(config)
            
            # Close default_action block
            hcl.append("  }")

            # Add tags if present
            tags = resource.get("tags", [])
            if tags:
                hcl.append("  tags = {")
                for tag in tags:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        key = tag["Key"].replace('"', '\\"')
                        value = tag["Value"].replace('"', '\\"')
                        hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close resource block
            hcl.append("}")

            return "\n".join(hcl)

        except Exception as e:
            logger.error(f"Error generating HCL for ALB listener: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for ALB listener"""
        try:
            listener_arn = resource.get("arn")
            listener_id = resource.get("id")

            if not listener_arn or not listener_id:
                raise ListenerConfigError("Missing ARN or ID for listener import command")

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_lb_listener.listener_{listener_id} {listener_arn}"

        except Exception as e:
            logger.error(f"Error generating import command for ALB listener: {str(e)}")
            return None
