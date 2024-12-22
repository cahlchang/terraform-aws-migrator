from abc import ABC, abstractmethod
from typing import Dict, List, Any, Callable, Optional
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
        logger.debug(f"Initializing collector: {self.__class__.__name__}")

    @abstractmethod
    def get_service_name(self) -> str:
        """Return the AWS service name for this collector"""
        raise NotImplementedError("Subclasses must implement get_service_name")

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        """Return dictionary of resource types supported by this collector"""
        return {}

    @classmethod
    def get_type_display_name(cls, resource_type: str) -> str:
        """Get display name for a resource type"""
        resource_types = cls.get_resource_types()
        return resource_types.get(resource_type, resource_type)

    @property
    def client(self):
        if self._client is None:
            self._client = self.session.client(self.get_service_name())
            logger.debug(f"Created client for service: {self.get_service_name()}")
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
    def collect(self, target_resource_type: str = "") -> List[Dict[str, Any]]:
        """Collect resources for the service"""
        pass

    @staticmethod
    def extract_tags(tags: List[Dict[str, str]]) -> Dict[str, str]:
        """Convert AWS tags list to dictionary"""
        return {tag["Key"]: tag["Value"] for tag in tags} if tags else {}

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


class CollectorRegistry:
    """Registry for resource collectors"""

    def __init__(self):
        self.collectors = []

    def register(self, collector_class: type):
        """Register a collector class"""
        self.collectors.append(collector_class)
        return collector_class

    def get_collectors(self, session: boto3.Session) -> List[ResourceCollector]:
        """Get all collector instances with the given session"""
        logger.debug(f"Getting collectors, total registered: {len(self.collectors)}")
        instances = []
        for collector_cls in self.collectors:
            try:
                collector = collector_cls(session)
                instances.append(collector)
                logger.debug(f"Initialized collector: {collector_cls.__name__}")
            except Exception as e:
                logger.error(
                    f"Failed to initialize collector {collector_cls.__name__}: {e}"
                )
        return instances

    def iter_classes(self):
        """Iterator over collector classes"""
        return iter(self.collectors)

    def __iter__(self):
        """Make the registry iterable over collector classes"""
        return self.iter_classes()

    def __len__(self):
        """Get number of registered collectors"""
        return len(self.collectors)


# Global registry instance
registry = CollectorRegistry()


def register_collector(collector_class: type):
    """Decorator to register a collector class"""
    logger.debug(f"Registering collector class: {collector_class.__name__}")
    return registry.register(collector_class)
