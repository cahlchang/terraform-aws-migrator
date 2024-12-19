# terraform_aws_migrator/formatters/output_formatter.py

import json
import time
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.text import Text
import logging
from ..collectors.base import registry

logger = logging.getLogger(__name__)

def format_output(
    resources: Dict[str, List[Dict[str, Any]]], output_format: str = "text"
) -> str:
    try:
        if output_format == "json":
            return json.dumps(resources, indent=2, default=str)

        if not resources:
            return "No unmanaged resources found."

        output = []
        output.append("\nUnmanaged AWS Resources:")
        output.append("=" * 40)

        # リソースタイプごとのカウントを保持する辞書
        resource_counts = {}

        # コレクターマップの作成
        collectors = {
            collector_cls.get_service_name(): collector_cls
            for collector_cls in registry
        }

        # リソースをタイプごとにグループ化してカウント
        for service_name, service_resources in sorted(resources.items()):
            collector_cls = collectors.get(service_name)
            if not collector_cls:
                continue

            for resource in service_resources:
                resource_type = resource.get("type", "unknown")
                full_type = f"{service_name}.{resource_type}"
                if full_type not in resource_counts:
                    resource_counts[full_type] = []
                resource_counts[full_type].append(resource)

        # サマリーセクション
        output.append("\nResource Summary:")
        for full_type, resources_list in sorted(resource_counts.items()):
            service_name, resource_type = full_type.split(".", 1)
            collector_cls = collectors.get(service_name)

            if collector_cls:
                display_name = collector_cls.get_type_display_name(resource_type)
            else:
                display_name = full_type

            count = len(resources_list)
            output.append(f"- Found {count} unmanaged {display_name}")

        # 詳細セクション
        if output_format == "text":
            output.append("\nDetailed Resources:")
            for full_type, resources_list in sorted(resource_counts.items()):
                service_name, resource_type = full_type.split(".", 1)
                collector_cls = collectors.get(service_name)

                if collector_cls:
                    display_name = collector_cls.get_type_display_name(resource_type)
                else:
                    display_name = full_type

                output.append(f"\n{display_name}:")

                for resource in resources_list:
                    resource_id = resource.get("id", "N/A")
                    resource_arn = resource.get("arn", "N/A")

                    output.append(f"  ID: {resource_id}")
                    output.append(f"  ARN: {resource_arn}")

                    # Add details if present
                    details = resource.get("details", {})
                    if details:
                        output.append("  Details:")
                        for detail_key, value in sorted(details.items()):
                            output.append(f"    {detail_key}: {value}")

                    # Add tags if present
                    tags = resource.get("tags", [])
                    if tags:
                        output.append("  Tags:")
                        if isinstance(tags, list):
                            for tag in tags:
                                if isinstance(tag, dict):
                                    key = tag.get("Key", "N/A")
                                    value = tag.get("Value", "N/A")
                                    output.append(f"    {key}: {value}")
                        elif isinstance(tags, dict):
                            for tag_key, value in sorted(tags.items()):
                                output.append(f"    {tag_key}: {value}")
                    output.append("")  # 空行を追加

        return "\n".join(output)

    except Exception as e:
        logger.exception("Error formatting output")
        return f"Error formatting output: {str(e)}"
