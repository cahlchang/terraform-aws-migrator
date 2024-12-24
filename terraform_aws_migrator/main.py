import argparse
import logging
import traceback
from rich.console import Console
from terraform_aws_migrator.utils.resource_utils import show_supported_resources
from terraform_aws_migrator.auditor import AWSResourceAuditor
from terraform_aws_migrator.formatters.output_formatter import format_output
from terraform_aws_migrator.generators import HCLGeneratorRegistry


def setup_logging(debug: bool = False):
    """Configure logging settings"""

    # Always suppress boto3/botocore logs unless in debug mode
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Set root logger to debug level if requested
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main():
    parser = argparse.ArgumentParser(
        description="Detect and migrate AWS resources that are not managed by Terraform"
    )
    parser.add_argument(
        "-t",
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
    parser.add_argument(
        "-i",
        "--ignore-file",
        type=str,
        help="Path to resource exclusion file (default: .tfignore)",
        metavar="FILE",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # HCL generation arguments
    parser.add_argument(
        "--generate", action="store_true", help="Generate HCL for unmanaged resources"
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Resource type to generate HCL for (e.g., aws_iam_role)",
    )
    parser.add_argument(
        "--module-prefix",
        type=str,
        help="Module prefix for import commands (e.g., 'my_module')"
    )
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
        # HCL generation mode
        if args.generate:
            if not args.type:
                console.print("[red]Error: --type is required when using --generate")
                return 1

            if not HCLGeneratorRegistry.is_supported(args.type):
                console.print(
                    f"[yellow]Warning: Resource type '{args.type}' is not yet supported for HCL generation"
                )
                return 1

            auditor = AWSResourceAuditor(
                exclusion_file=args.ignore_file, target_resource_type=args.type
            )
            unmanaged_resources = auditor.audit_specific_resource(
                args.tf_dir, args.type
            )
            # Get generator with module prefix if specified
            generator = HCLGeneratorRegistry.get_generator(
                args.type,
                module_prefix=args.module_prefix
            )
            console.print(f"Generating HCL for {len(unmanaged_resources)} {args.type} resources")

            import_txt = ""
            for resource_id, resource in unmanaged_resources.items():
                if isinstance(resource, dict):
                    hcl = generator.generate(resource)
                    import_cmd = generator.generate_import(resource)
                    if hcl:
                        if args.output_file:
                            with open(args.output_file, "a") as f:
                                f.write(hcl + "\n\n")
                        else:
                            console.print(hcl)
                    if import_cmd:
                        import_txt += import_cmd + "\n"

            if args.output_file:
                with open(args.output_file, "a") as f:
                    f.write(import_txt + "\n\n")
            else:
                console.print(import_txt)

        else:
            # Normal mode
            auditor = AWSResourceAuditor(exclusion_file=args.ignore_file)
            unmanaged_resources = auditor.audit_all_resources(args.tf_dir)

            # Format and display the output
            formatted_output = format_output(unmanaged_resources, args.output)

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
        console.print(f"[red]Error during detection: {traceback.format_exc()}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
