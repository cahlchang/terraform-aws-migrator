# terraform_aws_migrator/main.py

import argparse
import logging
import traceback
from rich.console import Console
from terraform_aws_migrator.utils.resource_utils import show_supported_resources
from terraform_aws_migrator.auditor import AWSResourceAuditor
from terraform_aws_migrator.formatters.output_formatter import format_output
from terraform_aws_migrator.generators import HCLGeneratorRegistry


logger = logging.getLogger(__name__)

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
        "--tf-dir",
        type=str,
        help="Directory containing Terraform files"
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
        "--list-resources",
        action="store_true",
        help="List supported resource types"
    )
    parser.add_argument(
        "-i",
        "--ignore-file",
        type=str,
        help="Path to resource exclusion file (default: .tfignore)",
        metavar="FILE",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Resource type to audit/generate (e.g., aws_iam_role)",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate HCL for unmanaged resources"
    )
    parser.add_argument(
        "--module-prefix",
        type=str,
        help="Module prefix for import commands (e.g., 'my_module')"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--include-default-vpc",
        action="store_true",
        help="Include default VPC in the generation (only applies to aws_vpc resources)"
    )
    parser.add_argument(
        "--include-managed",
        action="store_true",
        help="Include resources that are already managed by Terraform in HCL generation"
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
                    f"[yellow]Warning: Resource type or category '{args.type}' is not yet supported for HCL generation"
                )
                return 1

            # category mode
            if not args.type.startswith("aws_"):
                generators = HCLGeneratorRegistry.get_generators_for_category(args.type)
                if not generators:
                    console.print(
                        f"[yellow]Warning: No generators found for category '{args.type}'"
                    )
                    return 1

                auditor = AWSResourceAuditor(
                    exclusion_file=args.ignore_file,
                    target_resource_type=args.type
                )
                
                resources_result = auditor.audit_resources(args.tf_dir)
                
                # Store all HCL and import commands
                all_hcl = []
                all_imports = []

                # Process resources for each generator in the category
                for resource_type, generator_class in generators.items():
                    target_resources = {}
                    
                    # Process both managed and unmanaged resources if include_managed is True
                    resource_groups = ["unmanaged"]
                    if args.include_managed:
                        resource_groups.append("managed")
                    
                    for group in resource_groups:
                        for service_name, service_resources in resources_result[group].items():
                            logger.debug(f"Processing service: {service_name} with {len(service_resources)} resources")
                            for resource in service_resources:
                                current_type = resource.get("type")
                                logger.debug(f"Checking resource type: {current_type} against {resource_type}")
                                if current_type == resource_type:
                                    resource_id = resource.get("id")
                                    if resource_id:
                                        status = "managed" if group == "managed" else "unmanaged"
                                        logger.info(f"Found {status} {resource_type}: {resource_id}")
                                        target_resources[resource_id] = resource  # Remove unnecessary deepcopy

                    if not target_resources:
                        logger.debug(f"No unmanaged resources found for type: {resource_type}")
                        continue

                    # Get generator instance
                    generator = generator_class(
                        module_prefix=args.module_prefix,
                        state_reader=auditor.state_reader
                    )

                    # Collect HCL
                    type_hcl = []
                    for resource_id, resource in target_resources.items():
                        logger.info(f"Generating HCL for {resource.get('type')} - {resource_id}")
                        logger.debug(f"Resource details before generation: {resource}")
                        logger.debug(f"Resource details content: {resource.get('details', {})}")
                        logger.debug(f"Resource type: {type(resource.get('details', {}))}")
                        hcl = generator.generate(resource)
                        if hcl:
                            logger.info(f"Successfully generated HCL for {resource_id}")
                            logger.debug(f"Generated HCL:\n{hcl}")
                            type_hcl.append(hcl)
                        else:
                            logger.warning(f"Failed to generate HCL for {resource_id}")

                    if type_hcl:
                        logger.info(f"Adding {len(type_hcl)} HCL blocks for {resource_type}")
                        all_hcl.extend(type_hcl)
                    else:
                        logger.warning(f"No HCL generated for {resource_type}")

                    # Collect import commands
                    for resource_id, resource in target_resources.items():
                        import_cmd = generator.generate_import(resource)
                        if import_cmd:
                            all_imports.append(import_cmd)

                # Output all HCL first
                if all_hcl:
                    hcl_content = "\n\n".join(all_hcl)
                    if args.output_file:
                        with open(args.output_file, "a") as f:
                            f.write(hcl_content + "\n\n")
                    else:
                        console.print(hcl_content)

                # Then output all import commands
                if all_imports:
                    import_content = "\n".join(all_imports)
                    if args.output_file:
                        with open(args.output_file, "a") as f:
                            f.write("\n# Import commands\n" + import_content + "\n")
                    else:
                        console.print("\n# Import commands")
                        console.print(import_content)

            else:
                # complete resource type mode
                auditor = AWSResourceAuditor(
                    exclusion_file=args.ignore_file,
                    target_resource_type=args.type
                )
                
                resources_result = auditor.audit_resources(args.tf_dir)
                target_resources = {}
                
                # Process resources based on include_managed flag
                resource_groups = ["unmanaged"]
                if args.include_managed:
                    resource_groups.append("managed")

                for group in resource_groups:
                    for service_resources in resources_result[group].values():
                        for resource in service_resources:
                            if resource.get("type") == args.type:
                                resource_id = resource.get("id")
                                if resource_id:
                                    status = "managed" if group == "managed" else "unmanaged"
                                    logger.info(f"Found {status} {args.type}: {resource_id}")
                                    target_resources[resource_id] = resource  # Remove unnecessary deepcopy

                # Get generator with module prefix and state reader if specified
                generator = HCLGeneratorRegistry.get_generator(
                    args.type,
                    module_prefix=args.module_prefix,
                    state_reader=auditor.state_reader
                )

                console.print(f"Generating HCL for {len(target_resources)} {args.type} resources")

                # Store all HCL and import commands
                all_hcl = []
                all_imports = []

                # Collect HCL
                for resource_id, resource in target_resources.items():
                    # Pass include_default_vpc option for VPC resources
                    if args.type == "aws_vpc":
                        hcl = generator.generate(resource, include_default=args.include_default_vpc)
                    else:
                        hcl = generator.generate(resource)
                    if hcl:
                        all_hcl.append(hcl)

                # Collect import commands
                for resource_id, resource in target_resources.items():
                    import_cmd = generator.generate_import(resource)
                    if import_cmd:
                        all_imports.append(import_cmd)

                # Output all HCL first
                if all_hcl:
                    hcl_content = "\n\n".join(all_hcl)
                    if args.output_file:
                        with open(args.output_file, "a") as f:
                            f.write(hcl_content + "\n\n")
                    else:
                        console.print(hcl_content)

                # Then output all import commands
                if all_imports:
                    import_content = "\n".join(all_imports)
                    if args.output_file:
                        with open(args.output_file, "a") as f:
                            f.write("\n# Import commands\n" + import_content + "\n")
                    else:
                        console.print("\n# Import commands")
                        console.print(import_content)

        else:
            # Normal mode - now supports --type for filtering
            auditor = AWSResourceAuditor(
                exclusion_file=args.ignore_file,
                target_resource_type=args.type
            )
            resources_result = auditor.audit_resources(args.tf_dir)

            # Format and display the output
            formatted_output = format_output(resources_result["unmanaged"], args.output)

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
