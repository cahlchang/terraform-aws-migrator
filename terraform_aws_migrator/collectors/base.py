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

    @abstractmethod
    def get_service_name(self) -> str:
        """Return the AWS service name for this collector"""
        raise NotImplementedError("Subclasses must implement get_service_name")

    @classmethod
    def get_resource_types(cls) -> Dict[str, str]:
        """Return dictionary of resource types supported by this collector"""
        return {}

    @classmethod
    def get_service_for_resource_type(cls, resource_type: str) -> str:
        """
        Return the AWS service name for a resource type

        Args:
            resource_type: AWS resource type (e.g., aws_vpc, aws_subnet)
        Returns:
            Service name (e.g., ec2, s3)
        """
        # Special handling for EC2 service
        ec2_prefixes = [
            "aws_vpc", "aws_subnet", "aws_instance", "aws_ebs_volume",
            "aws_internet_gateway", "aws_nat_gateway", "aws_network_acl",
            "aws_route", "aws_route_table", "aws_vpc_dhcp_options",
            "aws_vpc_endpoint"
        ]
        if any(resource_type.startswith(prefix) for prefix in ec2_prefixes):
            return "ec2"

        # General case: aws_<service>_* or aws_<service>
        if resource_type.startswith("aws_"):
            parts = resource_type[4:].split("_", 1)
            return parts[0]

        return ""

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

    @classmethod
    def get_resource_service_mappings(cls) -> Dict[str, str]:
        """Return dictionary of resource type to service name mappings"""
        return {}

    def build_arn(self, resource_type: str, resource_id: str) -> str:
        """Build ARN for a resource"""
        service = self.get_service_name()
        account = self.account_id
        region = self.region

        # Determine service based on resource type
        if resource_type == "bucket":
            return f"arn:aws:s3:::{resource_id}"
        elif resource_type.startswith("role") or resource_type.startswith("policy"):
            return f"arn:aws:iam::{account}:{resource_type}/{resource_id}"
        elif service == "ec2":
            return f"arn:aws:ec2:{region}:{account}:{resource_type}/{resource_id}"
        else:
            return f"arn:aws:{service}:{region}:{account}:{resource_type}/{resource_id}"

    def generate_resource_identifier(self, resource: Dict[str, Any]) -> str:
        """
        Generate a standardized resource identifier

        Args:
            resource: Dictionary containing resource information
        Returns:
            Unique resource identifier
        """
        resource_type = resource.get("type")
        resource_id = resource.get("id")
        
        # Use ARN if available
        if "arn" in resource:
            return resource["arn"]
            
        # Special handling for IAM resources
        if resource_type and resource_type.startswith("aws_iam_"):
            if resource_type == "aws_iam_role_policy_attachment":
                role_name = resource.get("role")
                policy_arn = resource.get("policy_arn")
                if role_name and policy_arn:
                    return f"arn:aws:iam::{self.account_id}:role/{role_name}/{policy_arn}"
            elif resource_type == "aws_iam_user_policy":
                user_name = resource.get("user")
                policy_name = resource.get("name")
                if user_name and policy_name:
                    return f"{user_name}:{policy_name}"
            elif resource_type == "aws_iam_user_policy_attachment":
                user_name = resource.get("user")
                policy_arn = resource.get("policy_arn")
                if user_name and policy_arn:
                    return f"{user_name}:{policy_arn}"
        
        # Special handling for VPC endpoints
        if resource_type == "aws_vpc_endpoint":
            try:
                details = resource.get("details", {})
                vpc_id = details.get("vpc_id")
                service_name = details.get("service_name")
                endpoint_id = resource.get("id")

                # Output debug information
                logger.debug(f"Generating identifier for VPC endpoint:")
                logger.debug(f"  vpc_id: {vpc_id}")
                logger.debug(f"  service_name: {service_name}")
                logger.debug(f"  endpoint_id: {endpoint_id}")
                logger.debug(f"  details: {details}")

                # Get Name tag (first from details, then from tags)
                name = details.get("name")
                if not name:
                    tags = resource.get("tags", [])
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, dict) and tag.get("Key") == "Name":
                                name = tag.get("Value")
                                break

                # Use endpoint ID as primary identifier if available
                if endpoint_id:
                    # Basic identifier
                    identifier = f"{resource_type}:{endpoint_id}"
                    
                    # Generate more detailed identifier if additional information is available
                    if name and vpc_id and service_name:
                        identifier = f"{resource_type}:{name}:{vpc_id}:{service_name}:{endpoint_id}"
                    elif vpc_id and service_name:
                        identifier = f"{resource_type}:{vpc_id}:{service_name}:{endpoint_id}"

                logger.debug(f"Generated identifier for VPC endpoint: {identifier}")
                return identifier

            except Exception as e:
                logger.error(f"Error generating identifier for VPC endpoint: {str(e)}")
                logger.debug("Resource data:", exc_info=True)
                logger.debug(f"Resource: {resource}")
                return None

        # Basic identifier generation
        if resource_type and resource_id:
            # Tag-based identifier (prioritize Name tag)
            name_tag = None
            tags = resource.get("tags", [])
            if isinstance(tags, dict):
                name_tag = tags.get("Name")
            elif isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("Key") == "Name":
                        name_tag = tag.get("Value")
                        break
        
            if name_tag:
                return f"{resource_type}:{name_tag}:{resource_id}"
            return f"{resource_type}:{resource_id}"
                
        # Fallback: ID only
        return resource_id if resource_id else ""


def some_utility_function(data: Dict[str, Any]) -> Dict[str, Any]:
    return {f"{k}_transformed": f"{v}_transformed" for k, v in data.items()}


class CollectorRegistry:
    """Registry for resource collectors"""

    def __init__(self):
        self.collectors = []

    def register(self, collector_class: type):
        """Register a collector class"""
        self.collectors.append(collector_class)
        return collector_class

    def get_collectors(self, session: boto3.Session, target_type: str = "") -> List[ResourceCollector]:
        """
        Get collector instances with the given session, optionally filtered by target type.
        target_type can be either a full resource type (e.g. aws_s3_bucket) or a service category (e.g. s3)
        """
        logger.debug(f"Getting collectors, total registered: {len(self.collectors)}")
        instances = []
        for collector_cls in self.collectors:
            try:
                collector = collector_cls(session=session)
                # category or resource type filter
                if target_type:
                    resource_types = collector.get_resource_types()
                    service_name = collector.get_service_name()
                    if target_type != service_name and target_type not in resource_types:
                        continue
                instances.append(collector)
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


def register_collector(collector_class: type) -> type:
    """Decorator to register a collector class"""
    return registry.register(collector_class)
