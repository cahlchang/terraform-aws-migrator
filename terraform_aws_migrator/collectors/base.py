# terraform_aws_migrator/collectors/base.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Callable, Optional, Iterator
import boto3
import logging

logger = logging.getLogger(__name__)


class ResourceCollector(ABC):
    """Base class for AWS resource collectors"""

    def __init__(
        self,
        session: boto3.Session = None,
        progress_callback: Optional[Callable] = None,
    ):
        self._client = None
        self._account_id = None
        self._region = None
        self.session = session or boto3.Session()
        self.progress_callback = progress_callback

    @abstractmethod
    def get_service_name(self) -> str:
        """Return the AWS service name for this collector"""
        raise NotImplementedError("Subclasses must implement get_service_name")

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        """Return dictionary of resource types and their display names.

        Returns:
            Dict[str, str]: Mapping of resource type identifiers to human-readable names
            Example: {"aws_iam_role": "IAM Roles"}
        """
        return {}

    @classmethod
    def get_type_display_name(cls, resource_type: str) -> str:
        """Get the display name for a specific resource type

        Args:
            resource_type: The type identifier of the resource

        Returns:
            str: Human-readable display name for the resource type
        """
        return cls.get_resource_types().get(resource_type, resource_type)

    @property
    def client(self):
        if self._client is None:
            self._client = self.session.client(self.get_service_name())
        return self._client

    @property
    def account_id(self):
        if self._account_id is None:
            self._account_id = self.session.client("sts").get_caller_identity()[
                "Account"
            ]
        return self._account_id

    @property
    def region(self):
        """Get current AWS region"""
        if self._region is None:
            self._region = self.session.region_name
        return self._region

    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """Collect resources for the service"""
        pass

    @staticmethod
    def extract_tags(tags: List[Dict[str, str]]) -> Dict[str, str]:
        """Convert AWS tags list to dictionary"""
        return {tag["Key"]: tag["Value"] for tag in tags} if tags else {}

    def get_resource_types(self) -> Dict[str, str]:
        """Return dictionary of resource types supported by this collector"""
        return {}

    def build_arn(self, resource_type: str, resource_id: str) -> str:
        """Build ARN for a resource"""
        service = self.get_service_name()
        account = self.account_id
        region = self.region

        if service == "s3":
            return f"arn:aws:s3:::{resource_id}"
        elif service == "iam":
            return f"arn:aws:iam::{account}:{resource_type}/{resource_id}"
        else:
            return f"arn:aws:{service}:{region}:{account}:{resource_type}/{resource_id}"


class ResourceRegistry:
    """Registry for resource collectors"""

    def __init__(self):
        self._collector_classes = []

    def register(self, collector_class: type):
        """Register a collector class"""
        try:
            self._collector_classes.append(collector_class)
        except Exception as e:
            logger.error(
                f"Failed to register collector {collector_class.__name__}: {str(e)}"
            )

    def __iter__(self) -> Iterator[type]:
        """Make the registry iterable to return collector classes"""
        return iter(self._collector_classes)

    def __len__(self) -> int:
        """Return the number of registered collector classes"""
        return len(self._collector_classes)

    def collect_all(
        self,
        session: boto3.Session,
        progress_callback: Optional[Callable[[str, str, Optional[int]], None]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect resources from all registered collectors

        Args:
            session: boto3.Session to use for AWS API calls
            progress_callback: Callback function that takes (service_name, status, resource_count)

        Returns:
            Dict[str, List[Dict[str, Any]]]: Resources grouped by service
        """
        results = {}
        processed_services = set()

        for collector_class in self._collector_classes:
            try:
                collector = collector_class(session)
                service_name = collector.get_service_name()

                # Skip if we've already processed this service
                if service_name in processed_services:
                    continue
                processed_services.add(service_name)

                if progress_callback:
                    progress_callback(service_name, "Starting", None)

                logger.info(f"Collecting resources for service: {service_name}")
                resources = collector.collect()

                if progress_callback:
                    progress_callback(service_name, "Completed", len(resources))

                if resources:
                    results[service_name] = resources

            except Exception as e:
                error_msg = f"Error collecting {service_name} resources: {str(e)}"
                logger.error(error_msg)
                if progress_callback:
                    progress_callback(service_name, "Failed", 0)

        return results


# Global registry instance
registry = ResourceRegistry()


def register_collector(collector_class: type):
    """Decorator to register a collector class"""
    registry.register(collector_class)
    return collector_class
