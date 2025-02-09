from typing import Dict, List, Any, Optional
import logging
import copy

logger = logging.getLogger(__name__)

class ResourceManagementChecker:
    """Class responsible for checking if resources are managed by Terraform"""

    def __init__(self):
        self.processed_identifiers = set()

    def is_resource_managed(
        self,
        resource: Dict[str, Any],
        managed_lookup: Dict[str, Dict[str, Any]],
        collector: Any
    ) -> Optional[Dict[str, Any]]:
        """Check if a resource is managed by Terraform"""
        resource_type = resource.get("type")
        resource_identifier = collector.generate_resource_identifier(resource)

        if not resource_identifier:
            logger.warning(f"Could not generate identifier for resource: {resource}")
            return None

        # Check for duplicate resources
        if resource_identifier in self.processed_identifiers:
            logger.debug(f"Skipping duplicate resource: {resource_identifier}")
            return None

        # Check different identifiers in sequence
        identifiers_to_check = [resource_identifier]
        if "arn" in resource:
            identifiers_to_check.append(resource["arn"])
        if resource_type and "id" in resource:
            identifiers_to_check.append(f"{resource_type}:{resource['id']}")

        # Check each identifier
        for identifier in identifiers_to_check:
            if identifier in managed_lookup:
                logger.debug(f"Found managed resource with identifier: {identifier}")
                return managed_lookup[identifier]
            logger.debug(f"No managed resource found for identifier: {identifier}")

        return None

    def create_managed_lookup(
        self,
        managed_resources: Dict[str, Dict[str, Any]],
        collector: Any
    ) -> Dict[str, Dict[str, Any]]:
        """Create lookup dictionary for managed resources"""
        managed_lookup: Dict[str, Dict[str, Any]] = {}
        
        for managed_resource in managed_resources.values():
            resource_type = managed_resource.get("type", "")
            if "." in resource_type:
                resource_type = resource_type.split(".")[-1]

            # Generate identifiers (multiple formats)
            identifiers = []

            # ARN-based identifier
            if "arn" in managed_resource:
                identifiers.append(managed_resource["arn"])

            # Resource type and ID based identifier
            elif resource_type and "id" in managed_resource:
                identifier = f"{resource_type}:{managed_resource['id']}"
                identifiers.append(identifier)
            # Custom identifier
            else:
                managed_copy = managed_resource.copy()
                managed_copy["type"] = resource_type
                custom_identifier = collector.generate_resource_identifier(managed_copy)
                if custom_identifier:
                    identifiers.append(custom_identifier)

            # Remove duplicates and add as managed resource
            if identifiers:
                managed_copy = copy.deepcopy(managed_resource)
                managed_copy["managed"] = True
                for identifier in set(identifiers):
                    managed_lookup[identifier] = managed_copy
                    logger.debug(f"Added managed resource to lookup: {identifier} (type: {resource_type})")

        return managed_lookup

    def process_resource(
        self,
        resource: Dict[str, Any],
        managed_lookup: Dict[str, Dict[str, Any]],
        collector: Any
    ) -> Optional[Dict[str, Any]]:
        """Process a single resource and determine its management status"""
        resource_identifier = collector.generate_resource_identifier(resource)

        if not resource_identifier:
            return None

        # Check for duplicate resources first
        if resource_identifier in self.processed_identifiers:
            logger.debug(f"Skipping duplicate resource: {resource_identifier}")
            return None

        # Create resource copy
        resource_copy = copy.deepcopy(resource)
        resource_copy["identifier"] = resource_identifier
        
        # Check if resource is managed
        found_managed_resource = self.is_resource_managed(resource, managed_lookup, collector)
        if found_managed_resource is not None:
            # Use managed resource but keep details from collector
            resource_copy.update(found_managed_resource)
            resource_copy["details"] = resource.get("details", {})
            resource_copy["managed"] = True
            logger.debug(f"Resource {resource_identifier} marked as managed")
        else:
            resource_copy["managed"] = False
            logger.debug(f"Resource {resource_identifier} marked as unmanaged")

        self.processed_identifiers.add(resource_identifier)
        return resource_copy
