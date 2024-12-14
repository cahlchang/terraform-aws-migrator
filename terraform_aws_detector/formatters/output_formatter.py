# terraform_aws_detector/formatters/output_formatter.py

import json
from typing import Dict, List, Any

def format_output(resources: Dict[str, List[Dict[str, Any]]], output_format: str = 'text') -> str:
    if output_format == 'json':
        return json.dumps(resources, indent=2)
    
    # Text format
    output = []
    output.append("=== Terraform Unmanaged AWS Resources ===\n")
    
    for service, items in sorted(resources.items()):
        output.append(f"\n{service}:")
        for item in items:
            resource_id = item.get('id') or item.get('name')
            output.append(f"  - {resource_id}")
            output.append(f"    ARN: {item.get('arn', 'N/A')}")
            if 'tags' in item and item['tags']:
                output.append("    Tags:")
                for tag in item['tags']:
                    if isinstance(tag, dict):
                        output.append(f"      {tag.get('Key', 'N/A')}: {tag.get('Value', 'N/A')}")
            output.append("")
    
    return "\n".join(output)
