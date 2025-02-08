# terraform_aws_migrator/main.py

import argparse
import logging
import traceback
from rich.console import Console
from terraform_aws_migrator.utils.resource_utils import show_supported_resources
from terraform_aws_migrator.auditor import AWSResourceAuditor
from terraform_aws_migrator.formatters.output_formatter import format_output
from terraform_aws_migrator.generators import HCLGeneratorRegistry
from terraform_aws_migrator.collectors.base import registry as collector_registry
import boto3  # type: ignore

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False):
    """Configure logging settings"""
    level = logging.DEBUG if debug else logging.WARNING

    # Configure basic logging format and root logger level
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True
    )

    # Always suppress boto3/botocore logs
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Ensure terraform_aws_migrator logger and its children are set to the correct level
    app_logger = logging.getLogger("terraform_aws_migrator")
    app_logger.setLevel(level)
    
    # Propagate the level to all child loggers
    for name in logging.root.manager.loggerDict:
        if name.startswith("terraform_aws_migrator"):
            logging.getLogger(name).setLevel(level)


class ResourceProcessor:
    """Resource processing and filtering functionality"""

    @staticmethod
    def get_service_name(resource_type: str) -> str:
        """Get service name from resource type using collectors"""
        # Create a session for collector initialization
        session = boto3.Session()
        
        # Get all collectors that handle this resource type
        collectors = collector_registry.get_collectors(session, resource_type)
        
        for collector in collectors:
            # Check resource service mappings first
            service_mappings = collector.get_resource_service_mappings()
            if resource_type in service_mappings:
                return service_mappings[resource_type]
            
            # Check if the collector handles this resource type
            if resource_type in collector.get_resource_types():
                return collector.get_service_name()
        
        # Fallback: Extract service name from resource type
        if resource_type.startswith("aws_"):
            return resource_type.split("_")[1]
        return "other"

    @classmethod
    def process_resources(
        cls, resources_result: dict, resource_type: str, include_managed: bool = False
    ) -> dict:
        """Process and filter resources based on type and management status"""
        target_resources = {}
        service_name = cls.get_service_name(resource_type)
        logger.debug(f"Processing resources for service: {service_name}")

        if service_name in resources_result.get("all_resources", {}):
            logger.debug(
                f"Found {len(resources_result['all_resources'][service_name])} resources in service {service_name}"
            )
            for resource in resources_result["all_resources"][service_name]:
                if resource.get("type") == resource_type:
                    resource_id = resource.get("id")
                    if resource_id:
                        if not include_managed and resource.get("managed", False):
                            logger.debug(
                                f"Skipping managed resource {resource_type}: {resource_id}"
                            )
                            continue

                        target_resources[resource_id] = resource
                        status = (
                            "managed" if resource.get("managed", False) else "unmanaged"
                        )
                        logger.info(f"Found {status} {resource_type}: {resource_id}")
                        logger.debug(f"Resource details: {resource.get('details')}")

        logger.debug(f"Found {len(target_resources)} total resources")
        return target_resources


class HCLGenerator:
    """Handles HCL generation and output"""

    def __init__(self, console: Console, output_file: str | None = None):
        self.console = console
        self.output_file = output_file

    def write_output(self, content: str, header: str = ""):
        """Write content to file or console"""
        if self.output_file:
            with open(self.output_file, "a") as f:
                if header:
                    f.write(f"\n{header}\n")
                f.write(f"{content}\n")
        else:
            if header:
                self.console.print(header)
            self.console.print(content)

    def generate_category_hcl(
        self, generators: dict, resources_result: dict, args
    ) -> bool:
        """Generate HCL for a resource category"""
        all_hcl = []
        all_imports = []

        for resource_type, generator_class in generators.items():
            target_resources = ResourceProcessor.process_resources(
                resources_result, resource_type, args.include_managed
            )

            if not target_resources:
                continue

            generator = generator_class(
                module_prefix=args.module_prefix, state_reader=args.state_reader
            )

            for resource_id, resource in target_resources.items():
                logger.debug(f"Generating HCL for {resource_type} {resource_id}")
                logger.debug(f"Resource details: {resource.get('details', {})}")
                hcl = generator.generate(resource)
                if hcl:
                    all_hcl.append(hcl)
                import_cmd = generator.generate_import(resource)
                if import_cmd:
                    all_imports.append(import_cmd)

        if all_hcl:
            self.write_output("\n\n".join(all_hcl))
        if all_imports:
            self.write_output("\n".join(all_imports), "\n# Import commands")

        return bool(all_hcl or all_imports)

    def generate_resource_hcl(
        self,
        generator,
        target_resources: dict,
        resource_type: str,
        include_default_vpc: bool = False,
    ) -> bool:
        """Generate HCL for a specific resource type"""
        all_hcl = []
        all_imports = []

        for resource_id, resource in target_resources.items():
            logger.debug(f"Generating HCL for {resource_type} {resource_id}")
            logger.debug(f"Resource details: {resource.get('details', {})}")

            # Pass include_default parameter only for VPC resources
            if resource_type == "aws_vpc":
                hcl = generator.generate(resource, include_default=include_default_vpc)
            else:
                hcl = generator.generate(resource)

            if hcl:
                all_hcl.append(hcl)
            import_cmd = generator.generate_import(resource)
            if import_cmd:
                all_imports.append(import_cmd)

        if all_hcl:
            self.write_output("\n\n".join(all_hcl))
        if all_imports:
            self.write_output("\n".join(all_imports), "\n# Import commands")

        return bool(all_hcl or all_imports)


def validate_args(args: argparse.Namespace, console: Console) -> bool:
    """Validate command line arguments"""
    if args.list_resources:
        show_supported_resources()
        return False

    if not args.tf_dir:
        console.print(
            "[red]Error: --tf-dir is required when not using --list-resources[/red]"
        )
        return False

    if args.generate and not args.type:
        console.print("[red]Error: --type is required when using --generate")
        return False

    if args.generate and not HCLGeneratorRegistry.is_supported(args.type):
        console.print(
            f"[yellow]Warning: Resource type or category '{args.type}' is not yet supported for HCL generation"
        )
        return False

    return True


def handle_generation(args: argparse.Namespace, console: Console) -> int:
    """Handle HCL generation mode"""
    auditor = AWSResourceAuditor(
        exclusion_file=args.ignore_file, target_resource_type=args.type
    )
    resources_result = auditor.audit_resources(args.tf_dir)
    args.state_reader = auditor.state_reader
    hcl_generator = HCLGenerator(console, args.output_file)

    if not args.type.startswith("aws_"):
        generators = HCLGeneratorRegistry.get_generators_for_category(args.type)
        if not generators:
            console.print(
                f"[yellow]Warning: No generators found for category '{args.type}'"
            )
            return 1

        if not hcl_generator.generate_category_hcl(generators, resources_result, args):
            logger.warning(f"No HCL generated for category {args.type}")
            return 1
    else:
        target_resources = ResourceProcessor.process_resources(
            resources_result, args.type, args.include_managed
        )
        generator = HCLGeneratorRegistry.get_generator(
            args.type,
            module_prefix=args.module_prefix,
            state_reader=auditor.state_reader,
        )

        console.print(
            f"Generating HCL for {len(target_resources)} {args.type} resources"
        )
        if not hcl_generator.generate_resource_hcl(
            generator, target_resources, args.type, args.include_default_vpc
        ):
            logger.warning(f"No HCL generated for {args.type}")
            return 1

    return 0


def handle_detection(args: argparse.Namespace, console: Console) -> int:
    """Handle normal detection mode"""
    auditor = AWSResourceAuditor(
        exclusion_file=args.ignore_file, target_resource_type=args.type
    )
    resources_result = auditor.audit_resources(args.tf_dir)
    
    # Pass all resources to format_output
    formatted_output = format_output(resources_result.get("all_resources", {}), args.output)

    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(formatted_output)
        console.print(f"[green]Detection results written to {args.output_file}")
    else:
        console.print(formatted_output)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Detect and migrate AWS resources that are not managed by Terraform"
    )
    parser.add_argument(
        "-t", "--tf-dir", type=str, help="Directory containing Terraform files"
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
    parser.add_argument(
        "--type", type=str, help="Resource type to audit/generate (e.g., aws_iam_role)"
    )
    parser.add_argument(
        "--generate", action="store_true", help="Generate HCL for unmanaged resources"
    )
    parser.add_argument(
        "--module-prefix",
        type=str,
        help="Module prefix for import commands (e.g., 'my_module')",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--include-default-vpc",
        action="store_true",
        help="Include default VPC in the generation (only applies to aws_vpc resources)",
    )
    parser.add_argument(
        "--include-managed",
        action="store_true",
        help="Include resources that are already managed by Terraform in HCL generation",
    )

    args = parser.parse_args()
    setup_logging(args.debug)
    console = Console(stderr=True)

    try:
        if not validate_args(args, console):
            return 1

        return (
            handle_generation(args, console)
            if args.generate
            else handle_detection(args, console)
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Detection cancelled by user")
        return 1
    except Exception as e:
        console.print(f"[red]Error during detection: {str(e)}")
        console.print(f"[red]Error during detection: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit(main())
