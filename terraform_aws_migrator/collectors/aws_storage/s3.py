from typing import Dict, List, Any
from ..base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)


@register_collector
class S3Collector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "s3"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_s3_bucket": "S3 Buckets",
            "aws_s3_bucket_versioning": "S3 Bucket Versioning",
            "aws_s3_bucket_server_side_encryption_configuration": "S3 Bucket Encryption",
            "aws_s3_bucket_public_access_block": "S3 Bucket Public Access Block",
            "aws_s3_bucket_acl": "S3 Bucket ACL",
            "aws_s3_bucket_policy": "S3 Bucket Policy",
            "aws_s3_bucket_cors_configuration": "S3 Bucket CORS",
            "aws_s3_bucket_website_configuration": "S3 Bucket Website",
            "aws_s3_bucket_logging": "S3 Bucket Logging",
            "aws_s3_bucket_lifecycle_configuration": "S3 Bucket Lifecycle"
        }

    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        resources = []

        try:
            for bucket in self.client.list_buckets()["Buckets"]:
                bucket_name = bucket["Name"]
                try:
                    tags = self.client.get_bucket_tagging(Bucket=bucket_name).get(
                        "TagSet", []
                    )
                except:  # noqa: E722
                    tags = []

                # Get encryption configuration
                try:
                    encryption = self.client.get_bucket_encryption(Bucket=bucket_name)
                    encryption_rules = encryption.get('ServerSideEncryptionConfiguration', {}).get('Rules', [])
                    if encryption_rules:
                        encryption_config = encryption_rules[0].get('ApplyServerSideEncryptionByDefault', {})
                        encryption_details = {
                            "sse_algorithm": encryption_config.get('SSEAlgorithm'),
                            "kms_master_key_id": encryption_config.get('KMSMasterKeyID')
                        }
                except:  # noqa: E722
                    encryption_details = {}

                # Get ACL configuration
                # Get ACL configuration
                acl_details = None
                try:
                    acl = self.client.get_bucket_acl(Bucket=bucket_name)
                    if acl and isinstance(acl, dict):
                        owner = acl.get('Owner', {})
                        grants = acl.get('Grants', [])
                        if owner or grants:
                            acl_details = {
                                "owner": owner,
                                "grants": grants
                            }
                            logger.info(f"Successfully retrieved ACL for bucket: {bucket_name}")
                except self.client.exceptions.ClientError as e:
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    logger.warning(f"Error getting ACL for bucket {bucket_name}: Code={error_code}, Message={error_message}")
                except Exception as e:
                    logger.warning(f"Unexpected error getting ACL for bucket {bucket_name}: {str(e)}")

                # Get bucket policy
                try:
                    policy = self.client.get_bucket_policy(Bucket=bucket_name)
                    policy_text = policy.get('Policy')
                    if policy_text:
                        try:
                            # Verify that the policy is valid JSON
                            import json
                            json.loads(policy_text)
                            logger.info(f"Found valid bucket policy for {bucket_name}")
                            logger.debug(f"Policy content: {policy_text}")
                            
                            # Add only if policy exists and is valid JSON
                            resources.append({
                                "type": "aws_s3_bucket_policy",
                                "id": bucket_name,
                                "arn": f"arn:aws:s3:::{bucket_name}",  # Add ARN
                                "details": {
                                    "policy": policy_text
                                }
                            })
                            logger.info(f"Successfully added bucket policy for: {bucket_name}")
                        except json.JSONDecodeError as je:
                            logger.error(f"Invalid JSON in bucket policy for {bucket_name}: {je}")
                    else:
                        logger.warning(f"Empty policy returned for bucket: {bucket_name}")
                except self.client.exceptions.ClientError as e:
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    if error_code in ['NoSuchPolicy', 'NoSuchBucketPolicy']:
                        logger.debug(f"No bucket policy found for bucket: {bucket_name} (Code={error_code}, Message={error_message})")
                    else:
                        logger.warning(f"Unexpected error getting bucket policy for {bucket_name}: Code={error_code}, Message={error_message}")
                except Exception as e:
                    logger.warning(f"Unexpected error getting bucket policy for {bucket_name}: {str(e)}")

                # Get CORS configuration
                try:
                    cors = self.client.get_bucket_cors(Bucket=bucket_name)
                    cors_rules = cors.get('CORSRules', [])
                except:  # noqa: E722
                    cors_rules = []

                # Get website configuration
                try:
                    website = self.client.get_bucket_website(Bucket=bucket_name)
                    website_config = {
                        "index_document": website.get('IndexDocument', {}).get('Suffix'),
                        "error_document": website.get('ErrorDocument', {}).get('Key'),
                        "routing_rules": website.get('RoutingRules', [])
                    }
                except:  # noqa: E722
                    website_config = {}

                # Get logging configuration
                try:
                    logging = self.client.get_bucket_logging(Bucket=bucket_name)
                    logging_config = logging.get('LoggingEnabled', {})
                    if logging_config:
                        logging_details = {
                            "target_bucket": logging_config.get('TargetBucket'),
                            "target_prefix": logging_config.get('TargetPrefix')
                        }
                    else:
                        logging_details = {}
                except:  # noqa: E722
                    logging_details = {}

                # Get versioning configuration
                try:
                    versioning = self.client.get_bucket_versioning(Bucket=bucket_name)
                    versioning_status = versioning.get('Status')
                except:  # noqa: E722
                    versioning_status = None

                # Get public access block configuration
                try:
                    public_access = self.client.get_public_access_block(Bucket=bucket_name)
                    public_access_block = public_access.get('PublicAccessBlockConfiguration', {})
                except:  # noqa: E722
                    public_access_block = {}

                # Main bucket resource
                resources.append({
                    "type": "aws_s3_bucket",
                    "id": bucket_name,
                    "arn": f"arn:aws:s3:::{bucket_name}",
                    "tags": tags
                })

                # Versioning configuration
                if versioning_status:
                    resources.append({
                        "type": "aws_s3_bucket_versioning",
                        "id": bucket_name,
                        "details": {
                            "versioning_status": versioning_status
                        }
                    })

                # Encryption configuration
                if encryption_details:
                    resources.append({
                        "type": "aws_s3_bucket_server_side_encryption_configuration",
                        "id": bucket_name,
                        "details": encryption_details
                    })

                # Public access block configuration
                if public_access_block:
                    resources.append({
                        "type": "aws_s3_bucket_public_access_block",
                        "id": bucket_name,
                        "details": public_access_block
                    })

                # ACL configuration
                if acl_details and isinstance(acl_details, dict):
                    owner = acl_details.get("owner", {})
                    grants = acl_details.get("grants", [])
                    if owner or grants:
                        logger.info(f"Adding ACL resource for bucket: {bucket_name}")
                        resources.append({
                            "type": "aws_s3_bucket_acl",
                            "id": bucket_name,
                            "details": acl_details
                        })
                        logger.debug(f"ACL details for {bucket_name}: {acl_details}")

                # Bucket policy has already been added above

                # CORS configuration
                if cors_rules:
                    resources.append({
                        "type": "aws_s3_bucket_cors_configuration",
                        "id": bucket_name,
                        "details": {
                            "cors_rules": cors_rules
                        }
                    })

                # Website configuration
                if website_config.get("index_document") or website_config.get("error_document"):
                    resources.append({
                        "type": "aws_s3_bucket_website_configuration",
                        "id": bucket_name,
                        "details": website_config
                    })

                # Logging configuration
                if logging_details:
                    resources.append({
                        "type": "aws_s3_bucket_logging",
                        "id": bucket_name,
                        "details": logging_details
                    })
        except Exception as e:
            print(f"Error collecting S3 buckets: {str(e)}")

        return resources
