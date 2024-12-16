# terraform_aws_migrator/main.py

import argparse
import logging
from rich.console import Console
from terraform_aws_migrator.utils.resource_utils import show_supported_resources
from terraform_aws_migrator.auditor import AWSResourceAuditor

from terraform_aws_migrator.formatters.output_formatter import format_output

def setup_logging(debug: bool = False):
    """Configure logging settings"""
    # Suppress all loggers initially
    logging.getLogger().setLevel(logging.WARNING)
    
    # Suppress specific loggers
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('terraform_aws_migrator.collectors.base').setLevel(logging.WARNING)
    
    # Set debug level if requested
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('botocore').setLevel(logging.INFO)
        logging.getLogger('terraform_aws_migrator.collectors.base').setLevel(logging.DEBUG)

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

def main():
    parser = argparse.ArgumentParser(
        description="Migrate AWS resources that are not managed by Terraform"
    )
    parser.add_argument(
        "--tf-dir", type=str, help="Directory containing Terraform files"
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Output file path (optional, defaults to stdout)",
    )
    parser.add_argument(
        "--list-resources", action="store_true", help="List supported resource types"
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    setup_logging(args.debug)
    console = Console(stderr=True)

    # Show supported resources if requested
    if args.list_resources:
        show_supported_resources()
        return 0

    # Validate required arguments for resource detection
    if not args.tf_dir:
        console.print(
            "[red]Error: --tf-dir is required when not using --list-resources[/red]"
        )
        return 1

    try:
        # Run the detection
        auditor = AWSResourceAuditor()
        unmanaged_resources = auditor.audit_resources(args.tf_dir)

        # Format and display the output
        formatted_output = format_output(unmanaged_resources, args.output)

        # Write the output
        if args.output_file:
            with open(args.output_file, "w") as f:
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


if __name__ == "__main__":
    exit(main())
