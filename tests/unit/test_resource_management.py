import pytest
from terraform_aws_migrator.resource_management import ResourceManagementChecker

class MockCollector:
    def generate_resource_identifier(self, resource):
        if "custom_id" in resource:
            return f"custom:{resource['custom_id']}"
        elif "id" in resource:
            return f"{resource.get('type', 'unknown')}:{resource['id']}"
        return None

@pytest.fixture
def checker():
    return ResourceManagementChecker()

def test_is_resource_managed_with_direct_match():
    checker = ResourceManagementChecker()
    resource = {"type": "aws_instance", "id": "i-1234"}
    managed_lookup = {
        "aws_instance:i-1234": {"type": "aws_instance", "id": "i-1234", "managed": True}
    }
    collector = MockCollector()

    result = checker.is_resource_managed(resource, managed_lookup, collector)
    assert result is not None
    assert result["managed"] is True

def test_is_resource_managed_with_arn():
    checker = ResourceManagementChecker()
    resource = {
        "type": "aws_iam_role",
        "id": "role-1234",
        "arn": "arn:aws:iam::123456789012:role/test-role"
    }
    managed_lookup = {
        "arn:aws:iam::123456789012:role/test-role": {
            "type": "aws_iam_role",
            "id": "role-1234",
            "managed": True
        }
    }
    collector = MockCollector()

    result = checker.is_resource_managed(resource, managed_lookup, collector)
    assert result is not None
    assert result["managed"] is True

def test_is_resource_managed_with_custom_identifier():
    checker = ResourceManagementChecker()
    resource = {"type": "aws_custom", "custom_id": "custom-1234"}
    managed_lookup = {
        "custom:custom-1234": {"type": "aws_custom", "custom_id": "custom-1234", "managed": True}
    }
    collector = MockCollector()

    result = checker.is_resource_managed(resource, managed_lookup, collector)
    assert result is not None
    assert result["managed"] is True

def test_is_resource_managed_not_found():
    checker = ResourceManagementChecker()
    resource = {"type": "aws_instance", "id": "i-1234"}
    managed_lookup = {
        "aws_instance:i-5678": {"type": "aws_instance", "id": "i-5678", "managed": True}
    }
    collector = MockCollector()

    result = checker.is_resource_managed(resource, managed_lookup, collector)
    assert result is None

def test_create_managed_lookup():
    checker = ResourceManagementChecker()
    managed_resources = {
        "res1": {"type": "aws_instance", "id": "i-1234"},
        "res2": {"type": "aws_iam_role", "arn": "arn:aws:iam::123456789012:role/test-role"}
    }
    collector = MockCollector()

    lookup = checker.create_managed_lookup(managed_resources, collector)
    assert "aws_instance:i-1234" in lookup
    assert "arn:aws:iam::123456789012:role/test-role" in lookup
    assert all(res["managed"] for res in lookup.values())

def test_process_resource():
    checker = ResourceManagementChecker()
    resource = {"type": "aws_instance", "id": "i-1234", "details": {"name": "test"}}
    managed_lookup = {
        "aws_instance:i-1234": {
            "type": "aws_instance",
            "id": "i-1234",
            "managed": True,
            "extra": "data"
        }
    }
    collector = MockCollector()

    result = checker.process_resource(resource, managed_lookup, collector)
    assert result is not None
    assert result["managed"] is True
    assert result["details"] == {"name": "test"}
    assert result["extra"] == "data"
    assert result["identifier"] == "aws_instance:i-1234"

def test_process_resource_unmanaged():
    checker = ResourceManagementChecker()
    resource = {"type": "aws_instance", "id": "i-1234", "details": {"name": "test"}}
    managed_lookup = {}
    collector = MockCollector()

    result = checker.process_resource(resource, managed_lookup, collector)
    assert result is not None
    assert result["managed"] is False
    assert result["details"] == {"name": "test"}
    assert result["identifier"] == "aws_instance:i-1234"

def test_process_resource_duplicate():
    checker = ResourceManagementChecker()
    resource = {"type": "aws_instance", "id": "i-1234"}
    managed_lookup = {"aws_instance:i-1234": {"managed": True}}
    collector = MockCollector()

    # First process should succeed
    result1 = checker.process_resource(resource, managed_lookup, collector)
    assert result1 is not None

    # Second process of same resource should return None
    result2 = checker.process_resource(resource, managed_lookup, collector)
    assert result2 is None
