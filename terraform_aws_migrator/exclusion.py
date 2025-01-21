import fnmatch
import re
from pathlib import Path
from typing import List, Pattern, Optional
import logging

logger = logging.getLogger(__name__)

class ResourceExclusionConfig:
    """Handles the parsing and matching of resource exclusion patterns"""

    DEFAULT_FILENAME = ".tfignore"

    def __init__(self, exclusion_file: Optional[str] = None):
        self.exclusion_file = exclusion_file or self.DEFAULT_FILENAME
        self.patterns: List[str] = []
        self.regex_patterns: List[Pattern] = []
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load exclusion patterns from the configuration file"""
        try:
            config_path = Path(self.exclusion_file)
            if not config_path.exists():
                logger.debug(f"No exclusion file found at {self.exclusion_file}")
                return

            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        line = line.split("#")[0].strip()
                        if line:
                            self.patterns.append(line)
                            # Convert pattern to regex, handling service prefixes
                            pattern = self._convert_pattern_to_regex(line)
                            self.regex_patterns.append(re.compile(pattern))

            logger.info(f"Loaded {len(self.patterns)} exclusion patterns from {self.exclusion_file}")

        except Exception as e:
            logger.error(f"Error loading exclusion patterns: {str(e)}")
            self.patterns = []
            self.regex_patterns = []

    def _convert_pattern_to_regex(self, pattern: str) -> str:
        """Convert an exclusion pattern to regex, handling both AWS resource types and service prefixes"""
        if ":" in pattern:
            type_or_service, identifier = pattern.split(":", 1)
            # Convert glob pattern to regex
            identifier_pattern = fnmatch.translate(identifier)

            # Handle both aws_ prefixed and non-prefixed patterns
            if type_or_service.startswith("aws_"):
                # For exact AWS resource type matching
                return f"{type_or_service}:{identifier_pattern[:-2]}"
            else:
                # For service prefix matching (e.g., iam:)
                aws_prefix = f"aws_{type_or_service}"
                return f"(({type_or_service}:|{aws_prefix}.*:){identifier_pattern[:-2]})"
        else:
            # If no service prefix, just convert glob pattern
            return fnmatch.translate(pattern)[:-2]  # Remove \Z$ from fnmatch.translate()


    def should_exclude(self, resource: dict) -> bool:
            """
            Check if a resource should be excluded based on the patterns

            Args:
                resource (dict): Resource dictionary containing 'id', 'arn', 'type', 'tags', etc.

            Returns:
                bool: True if the resource should be excluded, False otherwise
            """
            if not self.patterns:
                return False

            # Values to check against patterns
            check_values = set()

            # Add basic identifiers
            resource_id = resource.get("id")
            if resource_id:
                check_values.add(resource_id)

            # Add ARN
            arn = resource.get("arn")
            if arn:
                check_values.add(arn)

            # Add type:id format and terraform resource name
            resource_type = resource.get("type")
            if resource_type and resource_id:
                # Remove 'aws_' prefix if present
                service_name = resource_type.replace("aws_", "", 1).split("_")[0]
                check_values.add(f"{service_name}:{resource_id}")
                # Also add the full type:id format
                check_values.add(f"{resource_type}:{resource_id}")
                
                # Add terraform resource name for EC2 instances
                if resource_type == "aws_instance":
                    name_tag_value = None
                    tags = resource.get("tags", [])
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, dict) and tag.get("Key") == "Name":
                                name_tag_value = tag.get("Value")
                                break
                    elif isinstance(tags, dict):
                        name_tag_value = tags.get("Name")
                    
                    if name_tag_value:
                        # Generate resource name in the same way as EC2InstanceGenerator
                        base_name = name_tag_value.replace("-", "_").replace(" ", "_")
                        short_id = resource_id[-4:] if resource_id else ""
                        terraform_resource_name = f"{base_name}_{short_id}"
                        check_values.add(terraform_resource_name)
                        check_values.add(f"{resource_type}:{terraform_resource_name}")

            # Add values from Name tag if present
            tags = resource.get("tags", [])
            name_tag_value = None
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("Key") == "Name":
                        name_tag_value = tag.get("Value")
                        break
            elif isinstance(tags, dict):
                name_tag_value = tags.get("Name")

            if name_tag_value:
                # Add name tag value directly
                check_values.add(name_tag_value)
                # Add service:name-tag format
                if resource_type:
                    service_name = resource_type.replace("aws_", "", 1).split("_")[0]
                    check_values.add(f"{service_name}:{name_tag_value}")
                    check_values.add(f"{resource_type}:{name_tag_value}")

            # Check each value against all patterns
            for value in check_values:
                for pattern in self.regex_patterns:
                    if pattern.search(str(value)):
                        logger.debug(f"Resource {value} excluded by pattern {pattern.pattern} (values checked: {check_values})")
                        return True

            return False

    def get_patterns(self) -> List[str]:
        """Return the current list of exclusion patterns"""
        return self.patterns.copy()
