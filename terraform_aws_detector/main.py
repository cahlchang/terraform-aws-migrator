# terraform_aws_detector/main.py

import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import boto3
import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

from terraform_aws_detector.collectors.base import registry
from terraform_aws_detector.collection_status import CollectionStatus
from terraform_aws_detector.state_reader import TerraformStateReader
from terraform_aws_detector.auditor import AWSResourceAuditor

from terraform_aws_detector.formatters.output_formatter import format_output
console = Console()

def main():
    parser = argparse.ArgumentParser(
        description='Detect AWS resources that are not managed by Terraform'
    )
    parser.add_argument('--tf-dir', type=str, required=True,
                       help='Directory containing Terraform files')
    parser.add_argument('--output', type=str, choices=['text', 'json'], default='text',
                       help='Output format (text or json)')
    parser.add_argument('--output-file', type=str,
                       help='Output file path (optional, defaults to stdout)')
    
    args = parser.parse_args()
    
    console = Console()
    
    try:
        # Run the detection
        auditor = AWSResourceAuditor()
        unmanaged_resources = auditor.audit_resources(args.tf_dir)
        
        # Format and display the output
        formatted_output = format_output(unmanaged_resources, args.output)
        
        # Write the output
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(formatted_output)
            console.print(f"[green]Detection results written to {args.output_file}")
        else:
            console.print(formatted_output)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Detection cancelled by user")
        return 1
    except Exception as e:
        console.print(f"[red]Error during detection: {str(e)}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
