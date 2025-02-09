import pytest
from rich.console import Console
from terraform_aws_migrator.resource_processor import ResourceProcessor

class MockCollector:
    def get_type_display_name(self, resource_type):
        return resource_type.replace("aws_", "").replace("_", " ").title()

@pytest.fixture
def processor():
    return ResourceProcessor(Console())

def test_group_resources_by_type(processor):
    resources = [
        {"type": "aws_instance", "id": "i-1234", "managed": True},
        {"type": "aws_instance", "id": "i-5678", "managed": False},
        {"type": "aws_s3_bucket", "id": "bucket-1", "managed": False}
    ]
    collector = MockCollector()
    elapsed_time_fn = lambda: "[00:01]"

    result = processor.group_resources_by_type(resources, collector, elapsed_time_fn)

    assert "aws_instance" in result
    assert "aws_s3_bucket" in result
    assert len(result["aws_instance"]) == 2
    assert len(result["aws_s3_bucket"]) == 1

def test_group_resources_by_type_empty_list(processor):
    result = processor.group_resources_by_type([], MockCollector(), lambda: "[00:00]")
    assert result == {}

def test_process_s3_resource_policy(processor):
    resource = {
        "type": "aws_s3_bucket_policy",
        "id": "bucket-1-policy"
    }
    managed_resources = {
        "res1": {
            "type": "aws_s3_bucket_policy",
            "id": "bucket-1-policy"
        }
    }

    result = processor.process_s3_resource(resource, managed_resources)
    assert result is True

def test_process_s3_resource_acl(processor):
    resource = {
        "type": "aws_s3_bucket_acl",
        "id": "bucket-1-acl"
    }
    managed_resources = {
        "res1": {
            "type": "aws_s3_bucket_acl",
            "id": "bucket-1-acl"
        }
    }

    result = processor.process_s3_resource(resource, managed_resources)
    assert result is True

def test_process_s3_resource_not_managed(processor):
    resource = {
        "type": "aws_s3_bucket_policy",
        "id": "bucket-1-policy"
    }
    managed_resources = {
        "res1": {
            "type": "aws_s3_bucket_policy",
            "id": "different-bucket-policy"
        }
    }

    result = processor.process_s3_resource(resource, managed_resources)
    assert result is False

def test_process_s3_resource_different_type(processor):
    resource = {
        "type": "aws_s3_bucket",
        "id": "bucket-1"
    }
    managed_resources = {}

    result = processor.process_s3_resource(resource, managed_resources)
    assert result is False

@pytest.mark.parametrize("resource_type,target_type,expected", [
    # target_type is None → No filter applied (all True)
    ("aws_instance", None, True),
    # 完全一致の場合
    ("aws_instance", "aws_instance", True),
    # 不一致の場合
    ("aws_instance", "aws_vpc", False),
    # "ec2" は "aws_instance" のシノニムとして扱われる
    ("aws_instance", "ec2", True),
    # "network" は "aws_vpc" のシノニムとして扱われる
    ("aws_vpc", "network", True),
    # resource_type が None の場合は常に False
    (None, "aws_instance", False),
    # target_type が空文字 → フィルタ指定なし (すべて True)
    ("aws_instance", "", True),
    # その他のマッピングケース
    ("aws_subnet", "network", True),
    ("aws_route", "network", True),
    ("aws_security_group", "ec2", True),
])
def test_matches_target_type(processor, resource_type, target_type, expected):
    result = processor.matches_target_type(resource_type, target_type)
    assert result == expected
