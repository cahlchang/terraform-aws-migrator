# terraform_aws_migrator/generators/aws_network/listener_rule.py

from typing import Dict, Any, Optional, List
import json
import logging
from ..base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class ALBListenerRuleGenerator(HCLGenerator):
    """Generator for aws_lb_listener_rule resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_lb_listener_rule"

    def _format_forward_action(self, action: Dict[str, Any]) -> str:
        """Format forward action with target groups and stickiness"""
        target_groups = action.get("ForwardConfig", {}).get("TargetGroups", [])
        stickiness = action.get("ForwardConfig", {}).get("TargetGroupStickinessConfig", {})
        if not target_groups:
            return ""

        blocks = ['    forward {']
        
        # Add target groups even with weight 0
        for tg in target_groups:
            blocks.extend([
                '      target_group {',
                f'        arn = "{tg.get("TargetGroupArn")}"',
                f'        weight = {tg.get("Weight", 0)}',
                '      }'
            ])

        # Add stickiness if present
        stickiness = action.get("ForwardConfig", {}).get("TargetGroupStickinessConfig", {})
        blocks.extend([
            '      stickiness {',
            f'        enabled = {str(stickiness.get("Enabled", True)).lower()}',
            f'        duration = {stickiness.get("DurationSeconds", stickiness.get("duration", 3600))}',  # Try to get DurationSeconds first, then duration, finally fallback to 3600
            '      }'
        ])

        blocks.append('    }')
        return '\n'.join(blocks)

    def _format_conditions(self, conditions: List[Dict[str, Any]]) -> str:
        """Format conditions block including http_header"""
        condition_blocks = []
        
        for condition in conditions:
            # HTTP Header condition
            if 'HttpHeaderConfig' in condition:
                config = condition['HttpHeaderConfig']
                condition_blocks.extend([
                    '  condition {',
                    '    http_header {',
                    f'      http_header_name = "{config["HttpHeaderName"]}"',
                    f'      values = {json.dumps(config["Values"])}',
                    '    }',
                    '  }'
                ])
            
            # Path Pattern condition
            elif 'PathPatternConfig' in condition:
                config = condition['PathPatternConfig']
                condition_blocks.extend([
                    '  condition {',
                    '    path_pattern {',
                    f'      values = {json.dumps(config["Values"])}',
                    '    }',
                    '  }'
                ])

            # Host Header condition
            elif 'HostHeaderConfig' in condition:
                config = condition['HostHeaderConfig']
                condition_blocks.extend([
                    '  condition {',
                    '    host_header {',
                    f'      values = {json.dumps(config["Values"])}',
                    '    }',
                    '  }'
                ])

        return '\n'.join(condition_blocks)

    def _format_tags(self, tags: List[Dict[str, str]]) -> Optional[str]:
        """Format resource tags"""
        if not tags:
            return None

        tag_blocks = ['  tags = {']
        for tag in tags:
            if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                key = tag["Key"].replace('"', '\\"')
                value = tag["Value"].replace('"', '\\"')
                tag_blocks.append(f'    "{key}" = "{value}"')
        tag_blocks.append('  }')
        return '\n'.join(tag_blocks)

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            rule_id = resource.get('id')
            details = resource.get('details', {})
            tags = resource.get('tags', [])
            listener_arn = details.get('listener_arn')
            priority = details.get('priority')
            actions = details.get('actions', [])
            conditions = details.get('conditions', [])

            if not all([rule_id, listener_arn, priority]):
                logger.error("Missing required fields for listener rule")
                return None

            # Start building HCL
            hcl_blocks = [
                f'resource "aws_lb_listener_rule" "rule_{rule_id}" {{',
                f'  listener_arn = "{listener_arn}"',
                f'  priority     = {priority}'
            ]

            # Add actions
            for action in actions:
                action_type = action.get('Type', '').lower()
                hcl_blocks.append('  action {')
                hcl_blocks.append(f'    type = "{action_type}"')
                
                if action_type == 'forward':
                    forward_config = self._format_forward_action(action)
                    if forward_config:
                        hcl_blocks.append(forward_config)
                
                hcl_blocks.append('  }')

            # Add conditions
            if conditions:
                condition_blocks = self._format_conditions(conditions)
                if condition_blocks:
                    hcl_blocks.append(condition_blocks)

            # Add tags if present
            tags_block = self._format_tags(tags)
            if tags_block:
                hcl_blocks.append(tags_block)

            hcl_blocks.append('}')
            return '\n'.join(hcl_blocks)

        except Exception as e:
            logger.error(f"Error generating HCL for listener rule: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for listener rule"""
        try:
            rule_arn = resource.get('arn')
            rule_id = resource.get('id')

            if not rule_arn or not rule_id:
                logger.error("Missing ARN or ID for listener rule import command")
                return None

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_lb_listener_rule.rule_{rule_id} {rule_arn}"

        except Exception as e:
            logger.error(f"Error generating import command for listener rule: {str(e)}")
            return None
