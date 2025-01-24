from typing import Dict, Any, Optional
import logging
import json
from terraform_aws_migrator.generators.base import HCLGenerator, register_generator

logger = logging.getLogger(__name__)

@register_generator
class S3BucketGenerator(HCLGenerator):
    """Generator for aws_s3_bucket resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_s3_bucket"

    def _generate_resource_name(self, bucket_name: str) -> str:
        """Generate a safe resource name from bucket name"""
        return bucket_name.replace("-", "_").replace(".", "_")

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                logger.error("Missing required bucket name")
                return None

            resource_name = self._generate_resource_name(bucket_name)
            hcl_blocks = []

            # Main bucket resource
            main_block = [
                f'resource "aws_s3_bucket" "{resource_name}" {{',
                f'  bucket = "{bucket_name}"',
                '  force_destroy = false  # Default to false for safety'
            ]

            # Add tags
            tags = resource.get("tags", [])
            if tags:
                main_block.append("  tags = {")
                for tag in tags:
                    if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                        key = tag["Key"].replace('"', '\\"')
                        value = tag["Value"].replace('"', '\\"')
                        main_block.append(f'    "{key}" = "{value}"')
                main_block.append("  }")

            main_block.append("}")
            return "\n".join(main_block)

        except Exception as e:
            logger.error(f"Error generating HCL for S3 bucket: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                logger.error("Missing bucket name for import command")
                return None

            resource_name = self._generate_resource_name(bucket_name)
            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_s3_bucket.{resource_name} {bucket_name}"

        except Exception as e:
            logger.error(f"Error generating import command for S3 bucket: {str(e)}")
            return None

@register_generator
class S3BucketACLGenerator(HCLGenerator):
    """Generator for aws_s3_bucket_acl resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_s3_bucket_acl"

    def _generate_resource_name(self, bucket_name: str) -> str:
        # Convert dots and underscores to hyphens first, then replace hyphens with underscores
        return bucket_name.replace(".", "-").replace("-", "_")

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            details = resource.get("details", {})
            if not details:
                return None

            owner = details.get("owner", {})
            grants = details.get("grants", [])

            hcl_blocks = [
                f'resource "aws_s3_bucket_acl" "{resource_name}" {{',
                f'  bucket = "{bucket_name}"',
                '  access_control_policy {',
            ]

            # Add owner block
            if owner:
                hcl_blocks.extend([
                    '    owner {',
                    f'      id = "{owner.get("ID", "")}"',
                    '    }',
                ])

            # Add grants
            if grants:
                for grant in grants:
                    grantee = grant.get("Grantee", {})
                    hcl_blocks.extend([
                        '    grant {',
                        f'      permission = "{grant.get("Permission", "")}"',
                        '',
                        '      grantee {',
                        f'        type = "{grantee.get("Type", "")}"',
                    ])
                    
                    # Add grantee details based on type
                    # display_nameは自動的に設定されるため、明示的に設定しない
                    if grantee.get("ID"):
                        hcl_blocks.append(f'        id = "{grantee.get("ID")}"')
                    if grantee.get("URI"):
                        hcl_blocks.append(f'        uri = "{grantee.get("URI")}"')
                    
                    hcl_blocks.extend([
                        '      }',
                        '    }',
                    ])

            hcl_blocks.extend([
                '  }',
                '}',
            ])

            return "\n".join(hcl_blocks)

        except Exception as e:
            logger.error(f"Error generating HCL for S3 bucket ACL: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_s3_bucket_acl.{resource_name} {bucket_name}"

        except Exception as e:
            logger.error(f"Error generating import command for S3 bucket ACL: {str(e)}")
            return None

@register_generator
class S3BucketPolicyGenerator(HCLGenerator):
    """Generator for aws_s3_bucket_policy resources"""

    @classmethod
    def resource_type(cls) -> str:
        logger.info("Registering S3BucketPolicyGenerator for aws_s3_bucket_policy")
        return "aws_s3_bucket_policy"

    def _generate_resource_name(self, bucket_name: str) -> str:
        name = bucket_name.replace("-", "_").replace(".", "_")
        logger.debug(f"Generated resource name for bucket {bucket_name}: {name}")
        return name

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        logger.info(f"Starting HCL generation for S3 bucket policy: {resource.get('id')}")
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            policy = resource.get("details", {}).get("policy")
            if not policy:
                return None

            # Ensure policy is properly formatted
            if isinstance(policy, str):
                try:
                    # バケットポリシーはすでにJSON文字列として取得されているため、
                    # 一度パースしてから使用します
                    policy_json = json.loads(policy)
                    logger.info(f"Successfully parsed policy for bucket {bucket_name}")
                    logger.debug(f"Policy content: {json.dumps(policy_json, indent=2)}")
                    
                    # ポリシーを整形して出力
                    formatted_policy = json.dumps(policy_json, indent=2)
                    hcl = [
                        f'resource "aws_s3_bucket_policy" "{resource_name}" {{',
                        f'  bucket = "{bucket_name}"',
                        '  policy = jsonencode(',
                        '    ' + formatted_policy.replace('\n', '\n    '),
                        '  )',
                        "}"
                    ]
                    
                    result = "\n".join(hcl)
                    logger.info(f"Generated HCL for bucket policy: {bucket_name}")
                    logger.debug(f"Generated HCL:\n{result}")
                    return result
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON policy string for bucket {bucket_name}: {e}")
                    return None
            else:
                logger.error(f"Policy must be a JSON string, got {type(policy)} for bucket {bucket_name}")
                logger.debug(f"Actual policy content: {policy}")
                return None

        except Exception as e:
            logger.error(f"Error generating HCL for S3 bucket policy: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_s3_bucket_policy.{resource_name} {bucket_name}"

        except Exception as e:
            logger.error(f"Error generating import command for S3 bucket policy: {str(e)}")
            return None

@register_generator
class S3BucketPublicAccessBlockGenerator(HCLGenerator):
    """Generator for aws_s3_bucket_public_access_block resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_s3_bucket_public_access_block"

    def _generate_resource_name(self, bucket_name: str) -> str:
        return bucket_name.replace("-", "_").replace(".", "_")

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            public_access = resource.get("details", {})
            if not public_access:
                return None

            return "\n".join([
                f'resource "aws_s3_bucket_public_access_block" "{resource_name}" {{',
                f'  bucket = "{bucket_name}"',
                f'  block_public_acls       = {str(public_access.get("block_public_acls", True)).lower()}',
                f'  block_public_policy     = {str(public_access.get("block_public_policy", True)).lower()}',
                f'  ignore_public_acls      = {str(public_access.get("ignore_public_acls", True)).lower()}',
                f'  restrict_public_buckets = {str(public_access.get("restrict_public_buckets", True)).lower()}',
                "}"
            ])

        except Exception as e:
            logger.error(f"Error generating HCL for S3 bucket public access block: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_s3_bucket_public_access_block.{resource_name} {bucket_name}"

        except Exception as e:
            logger.error(f"Error generating import command for S3 bucket public access block: {str(e)}")
            return None

@register_generator
class S3BucketCORSGenerator(HCLGenerator):
    """Generator for aws_s3_bucket_cors_configuration resources"""

    @classmethod
    def resource_type(cls) -> str:
        return "aws_s3_bucket_cors_configuration"

    def _generate_resource_name(self, bucket_name: str) -> str:
        return bucket_name.replace("-", "_").replace(".", "_")

    def generate(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            cors_rules = resource.get("details", {}).get("cors_rules", [])
            if not cors_rules:
                return None

            cors_block = [
                f'resource "aws_s3_bucket_cors_configuration" "{resource_name}" {{',
                f'  bucket = "{bucket_name}"'
            ]

            for rule in cors_rules:
                cors_block.append("  cors_rule {")
                if allowed_headers := rule.get("AllowedHeaders"):
                    cors_block.append(f'    allowed_headers = {json.dumps(allowed_headers)}')
                if allowed_methods := rule.get("AllowedMethods"):
                    cors_block.append(f'    allowed_methods = {json.dumps(allowed_methods)}')
                if allowed_origins := rule.get("AllowedOrigins"):
                    cors_block.append(f'    allowed_origins = {json.dumps(allowed_origins)}')
                if expose_headers := rule.get("ExposeHeaders"):
                    cors_block.append(f'    expose_headers = {json.dumps(expose_headers)}')
                if max_age_seconds := rule.get("MaxAgeSeconds"):
                    cors_block.append(f'    max_age_seconds = {max_age_seconds}')
                cors_block.append("  }")

            cors_block.append("}")
            return "\n".join(cors_block)

        except Exception as e:
            logger.error(f"Error generating HCL for S3 bucket CORS configuration: {str(e)}")
            return None

    def generate_import(self, resource: Dict[str, Any]) -> Optional[str]:
        try:
            bucket_name = resource.get("id")
            if not bucket_name:
                return None

            resource_name = self._generate_resource_name(bucket_name)
            prefix = self.get_import_prefix()
            return f"terraform import {prefix + '.' if prefix else ''}aws_s3_bucket_cors_configuration.{resource_name} {bucket_name}"

        except Exception as e:
            logger.error(f"Error generating import command for S3 bucket CORS configuration: {str(e)}")
            return None
