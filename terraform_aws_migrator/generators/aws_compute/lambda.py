# terraform_aws_migrator/generators/aws_compute/lambda.py

from typing import Dict, Any, Optional, List, Tuple, Union
import logging
import json
import base64
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)


@register_generator
class LambdaFunctionGenerator(HCLGenerator):
    """Generator for aws_lambda_function resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_lambda_function"

    def _get_name_from_tags(self, tags: Dict[str, str]) -> Optional[str]:
        """Get Name tag value from tags dictionary"""
        if isinstance(tags, dict):
            return tags.get("Name")
        return None

    def _generate_resource_name(self, resource: Dict[str, Any]) -> str:
        """Generate a safe resource name from function name"""
        function_name = resource.get("id", "")
        return function_name.replace("-", "_").replace(".", "_")

    def _get_lambda_code(self, code_location: Dict[str, Any]) -> Optional[str]:
        """Retrieve Lambda function code from code location"""
        if not code_location:
            return None

        try:
            if "ZipFile" in code_location:
                return base64.b64decode(code_location["ZipFile"]).decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Error retrieving Lambda code: {str(e)}")
            return None

    def _get_source_config(self, details: Dict[str, Any], resource_name: str) -> Tuple[List[str], Optional[Dict[str, str]]]:
        """Determine and format the appropriate source configuration"""
        package_type = details.get("package_type", "Zip")
        lines = []
        file_content = None

        if package_type == "Image":
            # For container images
            if image_uri := details.get("image_uri"):
                lines.append(f'  image_uri = "{image_uri}"')
            lines.append('  package_type = "Image"')
            return lines, None

        # For zip packages
        code_location = details.get("code", {})
        if s3_bucket := code_location.get("s3_bucket"):
            # S3 source
            lines.append(f'  s3_bucket = "{s3_bucket}"')
            if s3_key := code_location.get("s3_key"):
                lines.append(f'  s3_key = "{s3_key}"')
            if s3_object_version := code_location.get("s3_object_version"):
                lines.append(f'  s3_object_version = "{s3_object_version}"')
        else:
            # Try to get inline code
            if code := self._get_lambda_code(code_location):
                file_content = {
                    "index.py": code  # or index.js, depending on runtime
                }
                # Add archive configuration
                lines.extend([
                    '  filename = "${' + f'data.archive_file.{resource_name}_lambda.output_path' + '}"',
                    '  source_code_hash = "${' + f'data.archive_file.{resource_name}_lambda.output_base64sha256' + '}"'
                    f'  source_code_hash = data.archive_file.{resource_name}.output_base64sha256'
                ])

        return lines, file_content

    def _format_function_layers(self, layers: List[str]) -> str:
        """Format Lambda layers configuration"""
        if not layers:
            return ""
        layer_arns = '", "'.join(layers)
        return f'  layers = ["{layer_arns}"]'

    def _format_image_config(self, image_config: Dict[str, Any]) -> List[str]:
        """Format container image configuration"""
        if not image_config:
            return []

        lines = ["  image_config {"]
        
        if command := image_config.get("command"):
            commands = ", ".join(f'"{cmd}"' for cmd in command)
            lines.append(f"    command = [{commands}]")
            
        if entry_point := image_config.get("entry_point"):
            entry_points = ", ".join(f'"{ep}"' for ep in entry_point)
            lines.append(f"    entry_point = [{entry_points}]")
            
        if working_directory := image_config.get("working_directory"):
            lines.append(f'    working_directory = "{working_directory}"')

        lines.append("  }")
        return lines

    def _get_main_file_name(self, handler: Optional[str], runtime: str) -> str:
        """Get the main file name from handler and runtime"""
        # ハンドラーが有効な場合、そこからファイル名を抽出
        if handler and '.' in handler:
            file_base = handler.split('.')[0]
        else:
            # ハンドラーが無効な場合はデフォルトのファイル名を使用
            file_base = "index"
        
        # ランタイムに基づいて適切な拡張子を追加
        if runtime and "python" in runtime.lower():
            return f"{file_base}.py"
        elif runtime and "node" in runtime.lower():
            return f"{file_base}.js"
        else:
            # デフォルトはPython
            return f"{file_base}.py"

    def _generate_archive_file(self, resource_name: str, files: Dict[str, str], runtime: str, handler: Optional[str] = None) -> List[str]:
        """Generate archive_file data source configuration"""
        main_file = self._get_main_file_name(handler, runtime)

        lines = [
            f'data "archive_file" "{resource_name}_lambda" {{',
            '  type        = "zip"',
            f'  output_path = "${{path.module}}/files/{resource_name}.zip"',
            "",
            "  source {",
            f'    content  = <<EOF',
            files.get(main_file, "# Empty function"),
            'EOF',
            f'    filename = "{main_file}"',
            "  }",
            "}"
        ]
        return lines

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate HCL for a Lambda function"""
        try:
            function_name = resource.get("id")
            details = resource.get("details", {})

            if not function_name or not details:
                logger.error("Missing required Lambda function details")
                return None

            # Generate resource name
            resource_name = self._generate_resource_name(resource)

            # Get source configuration and potential inline code
            source_config, file_content = self._get_source_config(details, resource_name)

            # Start building HCL blocks
            hcl_blocks = []

            # Add archive_file data source if we have inline code
            if file_content:
                archive_block = self._generate_archive_file(
                    resource_name,
                    file_content,
                    details.get("runtime", ""),
                    details.get("handler", "")
                )
                hcl_blocks.extend(archive_block)
                hcl_blocks.append("")  # Add spacing

            # Start main Lambda resource
            hcl = [
                f'resource "aws_lambda_function" "{resource_name}" {{',
                f'  function_name = "{function_name}"',
                f'  role          = "{details.get("role")}"',
            ]

            # Add package type
            if package_type := details.get("package_type"):
                hcl.append(f'  package_type = "{package_type}"')

            # Add source configuration based on package type
            if package_type == "Image":
                if image_uri := details.get("image_uri"):
                    hcl.append(f'  image_uri = "{image_uri}"')
            else:
                # Add source configuration for Zip packages
                hcl.extend(source_config)
                # Add handler and runtime for zip packages
                if handler := details.get("handler"):
                    hcl.append(f'  handler = "{handler}"')
                if runtime := details.get("runtime"):
                    hcl.append(f'  runtime = "{runtime}"')

            # Add optional fields
            if description := details.get("description"):
                hcl.append(f'  description = "{description}"')

            if memory_size := details.get("memory_size"):
                hcl.append(f'  memory_size = {memory_size}')

            if timeout := details.get("timeout"):
                hcl.append(f'  timeout = {timeout}')

            # Always add publish parameter with default value false
            publish = details.get("publish", False)
            hcl.append(f'  publish = {str(publish).lower()}')

            # Add layers if present
            if layers := details.get("layers", []):
                layer_config = self._format_function_layers(layers)
                if layer_config:
                    hcl.append(layer_config)

            # Add environment variables
            environment = details.get("environment", {})
            if environment and environment.get("variables"):
                hcl.append("  environment {")
                hcl.append("    variables = {")
                for key, value in environment["variables"].items():
                    hcl.append(f'      {key} = "{value}"')
                hcl.append("    }")
                hcl.append("  }")

            # Add VPC configuration
            vpc_config = details.get("vpc_config", {})
            if vpc_config:
                hcl.append("  vpc_config {")
                if subnet_ids := vpc_config.get("subnet_ids", []):
                    subnet_ids_str = '", "'.join(subnet_ids)
                    hcl.append(f'    subnet_ids = ["{subnet_ids_str}"]')
                if security_group_ids := vpc_config.get("security_group_ids", []):
                    sg_ids_str = '", "'.join(security_group_ids)
                    hcl.append(f'    security_group_ids = ["{sg_ids_str}"]')
                hcl.append("  }")

            # Add dead letter config
            dead_letter_config = details.get("dead_letter_config", {})
            if dead_letter_config and (target_arn := dead_letter_config.get("target_arn")):
                hcl.append("  dead_letter_config {")
                hcl.append(f'    target_arn = "{target_arn}"')
                hcl.append("  }")

            # Add tracing config
            tracing_config = details.get("tracing_config", {})
            if tracing_config and (mode := tracing_config.get("mode")):
                hcl.append("  tracing_config {")
                hcl.append(f'    mode = "{mode}"')
                hcl.append("  }")

            # Add file system config if present
            file_system_config = details.get("file_system_config", {})
            if file_system_config:
                hcl.append("  file_system_config {")
                if arn := file_system_config.get("arn"):
                    hcl.append(f'    arn = "{arn}"')
                if local_mount_path := file_system_config.get("local_mount_path"):
                    hcl.append(f'    local_mount_path = "{local_mount_path}"')
                hcl.append("  }")

            # Add tags
            tags = resource.get("tags", {})
            if tags:
                hcl.append("  tags = {")
                for key, value in tags.items():
                    key = key.replace('"', '\\"')
                    value = value.replace('"', '\\"')
                    hcl.append(f'    "{key}" = "{value}"')
                hcl.append("  }")

            # Close resource block
            hcl.append("}")

            # Add the main resource block to our blocks
            hcl_blocks.extend(hcl)

            return "\n".join(hcl_blocks)

        except Exception as e:
            logger.error(f"Error generating HCL for Lambda function: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        """Generate import command for Lambda function"""
        try:
            function_name = resource.get("id")
            if not function_name:
                logger.error("Missing function name for import command")
                return None

            # Generate resource name matching the one in generate()
            resource_name = self._generate_resource_name(resource)

            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_lambda_function.{resource_name} {function_name}"

        except Exception as e:
            logger.error(f"Error generating import command for Lambda function: {str(e)}")
            return None
