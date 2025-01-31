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
    level = logging.DEBUG if debug else logging.WARNING
    logging.getLogger().setLevel(level)
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

class ResourceProcessor:
    """Resource processing and filtering functionality"""
    
    @staticmethod
    def extract_resource(item: dict, resource_type: str, management_state: str) -> tuple[str, dict] | None:
        """Extract resource ID and data if it matches the target type."""
        if item.get("type") == resource_type:
            resource_id = item.get("id")
            if resource_id:
                status = "managed" if management_state == "managed" else "unmanaged"
                logger.info(f"Found {status} {resource_type}: {resource_id}")
                return resource_id, item
        return None

    @classmethod
    def process_resource_data(cls, data: dict | list, resource_type: str, management_state: str) -> dict:
        """Process resource data and extract matching resources."""
        found_resources = {}
        
        items = data.values() if isinstance(data, dict) else data if isinstance(data, list) else []
        
        for item in items:
            if isinstance(item, dict):
                result = cls.extract_resource(item, resource_type, management_state)
                if result:
                    resource_id, resource = result
                    found_resources[resource_id] = resource
                found_resources.update(cls.process_resource_data(item, resource_type, management_state))
            elif isinstance(item, list):
                found_resources.update(cls.process_resource_data(item, resource_type, management_state))
        
        return found_resources

    @classmethod
    def process_resources(cls, resources_result: dict, resource_type: str, include_managed: bool = False) -> dict:
        """Process and filter resources based on type and management status"""
        target_resources = {}
        management_states = ["unmanaged", "managed"] if include_managed else ["unmanaged"]

        for state in management_states:
            if state in resources_result:
                target_resources.update(cls.process_resource_data(resources_result[state], resource_type, state))

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

    def generate_category_hcl(self, generators: dict, resources_result: dict, args) -> bool:
        """Generate HCL for a resource category"""
        all_hcl = []
        all_imports = []

        for resource_type, generator_class in generators.items():
            target_resources = {}
            resource_groups = ["unmanaged", "managed"] if args.include_managed else ["unmanaged"]
            
            for group in resource_groups:
                for service_name, service_resources in resources_result[group].items():
                    for resource in service_resources:
                        if resource.get("type") == resource_type:
                            resource_id = resource.get("id")
                            if resource_id:
                                target_resources[resource_id] = resource

            if not target_resources:
                continue

            generator = generator_class(
                module_prefix=args.module_prefix,
                state_reader=args.state_reader
            )

            for resource_id, resource in target_resources.items():
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

    def generate_resource_hcl(self, generator, target_resources: dict, resource_type: str, include_default_vpc: bool = False) -> bool:
        """Generate HCL for a specific resource type"""
        all_hcl = []
        all_imports = []

        for resource_id, resource in target_resources.items():
            # include_default パラメータはVPCリソースの場合のみ渡す
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
        console.print("[red]Error: --tf-dir is required when not using --list-resources[/red]")
        return False

    if args.generate and not args.type:
        console.print("[red]Error: --type is required when using --generate")
        return False

    if args.generate and not HCLGeneratorRegistry.is_supported(args.type):
        console.print(f"[yellow]Warning: Resource type or category '{args.type}' is not yet supported for HCL generation")
        return False

    return True

def handle_generation(args: argparse.Namespace, console: Console) -> int:
    """Handle HCL generation mode"""
    auditor = AWSResourceAuditor(
        exclusion_file=args.ignore_file,
        target_resource_type=args.type
    )
    resources_result = auditor.audit_resources(args.tf_dir)
    args.state_reader = auditor.state_reader
    hcl_generator = HCLGenerator(console, args.output_file)

    if not args.type.startswith("aws_"):
        generators = HCLGeneratorRegistry.get_generators_for_category(args.type)
        if not generators:
            console.print(f"[yellow]Warning: No generators found for category '{args.type}'")
            return 1
        
        if not hcl_generator.generate_category_hcl(generators, resources_result, args):
            logger.warning(f"No HCL generated for category {args.type}")
            return 1
    else:
        target_resources = ResourceProcessor.process_resources(resources_result, args.type, args.include_managed)
        generator = HCLGeneratorRegistry.get_generator(
            args.type,
            module_prefix=args.module_prefix,
            state_reader=auditor.state_reader
        )
        
        console.print(f"Generating HCL for {len(target_resources)} {args.type} resources")
        if not hcl_generator.generate_resource_hcl(generator, target_resources, args.type, args.include_default_vpc):
            logger.warning(f"No HCL generated for {args.type}")
            return 1

    return 0

def handle_detection(args: argparse.Namespace, console: Console) -> int:
    """Handle normal detection mode"""
    auditor = AWSResourceAuditor(
        exclusion_file=args.ignore_file,
        target_resource_type=args.type
    )
    resources_result = auditor.audit_resources(args.tf_dir)
    formatted_output = format_output(resources_result["unmanaged"], args.output)

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
    parser.add_argument("-t", "--tf-dir", type=str, help="Directory containing Terraform files")
    parser.add_argument("--output", type=str, choices=["text", "json"], default="text", help="Output format (text or json)")
    parser.add_argument("--output-file", type=str, help="Output file path (optional, defaults to stdout)")
    parser.add_argument("--list-resources", action="store_true", help="List supported resource types")
    parser.add_argument("-i", "--ignore-file", type=str, help="Path to resource exclusion file (default: .tfignore)", metavar="FILE")
    parser.add_argument("--type", type=str, help="Resource type to audit/generate (e.g., aws_iam_role)")
    parser.add_argument("--generate", action="store_true", help="Generate HCL for unmanaged resources")
    parser.add_argument("--module-prefix", type=str, help="Module prefix for import commands (e.g., 'my_module')")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--include-default-vpc", action="store_true", help="Include default VPC in the generation (only applies to aws_vpc resources)")
    parser.add_argument("--include-managed", action="store_true", help="Include resources that are already managed by Terraform in HCL generation")

    args = parser.parse_args()
    setup_logging(args.debug)
    console = Console(stderr=True)

    try:
        if not validate_args(args, console):
            return 1

        return handle_generation(args, console) if args.generate else handle_detection(args, console)

    except KeyboardInterrupt:
        console.print("\n[yellow]Detection cancelled by user")
        return 1
    except Exception as e:
        console.print(f"[red]Error during detection: {str(e)}")
        console.print(f"[red]Error during detection: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    exit(main())
