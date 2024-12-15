# terraform_aws_detector/main.py

import argparse
from rich.console import Console
from terraform_aws_detector.utils.resource_utils import show_supported_resources
from terraform_aws_detector.auditor import AWSResourceAuditor

from terraform_aws_detector.formatters.output_formatter import format_output


def main():
    parser = argparse.ArgumentParser(
        description="Detect AWS resources that are not managed by Terraform"
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

    args = parser.parse_args()
    console = Console(stderr=False, file=None)

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
