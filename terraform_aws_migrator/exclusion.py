# terraform_aws_migrator/exclusion.py

from pathlib import Path
from typing import List, Set, Pattern
import re
import fnmatch
import logging

logger = logging.getLogger(__name__)


class ResourceExclusionConfig:
    """Handles the parsing and matching of resource exclusion patterns"""

    DEFAULT_FILENAME = ".tfignore"  # Changed from .tfawsignore to .tfignore

    def __init__(self, exclusion_file: str = None):
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
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        # Add support for inline comments
                        line = line.split("#")[0].strip()
                        if line:  # Check again after removing comments
                            self.patterns.append(line)
                            # Convert glob pattern to regex
                            regex_pattern = fnmatch.translate(line)
                            self.regex_patterns.append(re.compile(regex_pattern))

            logger.info(
                f"Loaded {len(self.patterns)} exclusion patterns from {self.exclusion_file}"
            )

        except Exception as e:
            logger.error(f"Error loading exclusion patterns: {str(e)}")
            self.patterns = []
            self.regex_patterns = []

    def should_exclude(self, resource: dict) -> bool:
        """
        Check if a resource should be excluded based on the patterns

        Args:
            resource (dict): Resource dictionary containing 'id', 'arn', and other attributes

        Returns:
            bool: True if the resource should be excluded, False otherwise
        """
        if not self.patterns:
            return False

        # Values to check against patterns
        check_values = set()

        # Add resource ID
        if "id" in resource:
            check_values.add(resource["id"])

        # Add ARN
        if "arn" in resource:
            check_values.add(resource["arn"])

        # Add type:id format
        if "type" in resource and "id" in resource:
            check_values.add(f"{resource['type']}:{resource['id']}")

        # Add service:id format for more specific matching
        if "service" in resource and "id" in resource:
            check_values.add(f"{resource['service']}:{resource['id']}")

        # Check if any value matches any pattern
        for value in check_values:
            for pattern in self.regex_patterns:
                if pattern.match(str(value)):
                    logger.debug(
                        f"Resource {value} excluded by pattern {pattern.pattern}"
                    )
                    return True

        return False

    def get_patterns(self) -> List[str]:
        """Return the current list of exclusion patterns"""
        return self.patterns.copy()
