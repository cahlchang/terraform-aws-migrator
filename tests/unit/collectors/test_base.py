import pytest
from terraform_aws_migrator.collectors.base import ResourceCollector


class TestCollector(ResourceCollector):
    """テスト用のコレクタークラス"""
    def get_service_name(self) -> str:
        return "ec2"

    def collect(self, target_resource_type: str = ""):
        return []


def test_basic_identifier_generation(mock_session):
    """基本的なリソース識別子生成のテスト"""
    collector = TestCollector(mock_session)
    
    # ARNを持つリソース
    resource = {
        "type": "aws_vpc",
        "id": "vpc-12345678",
        "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    
    # ARNを持たないリソース
    resource = {
        "type": "aws_security_group",
        "id": "sg-12345678"
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "aws_security_group:sg-12345678"


def test_iam_resource_identifier_generation(mock_session):
    """IAMリソースの識別子生成テスト"""
    collector = TestCollector(mock_session)
    
    # ロールポリシーアタッチメント
    resource = {
        "type": "aws_iam_role_policy_attachment",
        "role": "test-role",
        "policy_arn": "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == f"arn:aws:iam::123456789012:role/test-role/arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    
    # ユーザーポリシー
    resource = {
        "type": "aws_iam_user_policy",
        "user": "test-user",
        "name": "test-policy"
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "test-user:test-policy"
    
    # ユーザーポリシーアタッチメント
    resource = {
        "type": "aws_iam_user_policy_attachment",
        "user": "test-user",
        "policy_arn": "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "test-user:arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"


def test_tag_based_identifier_generation(mock_session):
    """タグベースの識別子生成テスト"""
    collector = TestCollector(mock_session)
    
    # 辞書形式のタグ
    resource = {
        "type": "aws_vpc",
        "id": "vpc-12345678",
        "tags": {
            "Name": "MainVPC",
            "Environment": "Production"
        }
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "aws_vpc:MainVPC:vpc-12345678"
    
    # リスト形式のタグ
    resource = {
        "type": "aws_vpc",
        "id": "vpc-12345678",
        "tags": [
            {"Key": "Name", "Value": "MainVPC"},
            {"Key": "Environment", "Value": "Production"}
        ]
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "aws_vpc:MainVPC:vpc-12345678"


def test_edge_cases_identifier_generation(mock_session):
    """エッジケースの識別子生成テスト"""
    collector = TestCollector(mock_session)
    
    # 必須フィールドが欠けているリソース
    resource = {
        "id": "vpc-12345678"  # typeなし
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "vpc-12345678"
    
    resource = {
        "type": "aws_vpc"  # idなし
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == ""
    
    # 空のタグを持つリソース
    resource = {
        "type": "aws_vpc",
        "id": "vpc-12345678",
        "tags": {}
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "aws_vpc:vpc-12345678"
    
    # 無効なタグ形式
    resource = {
        "type": "aws_vpc",
        "id": "vpc-12345678",
        "tags": "invalid"
    }
    identifier = collector.generate_resource_identifier(resource)
    assert identifier == "aws_vpc:vpc-12345678"


def test_get_service_for_resource_type(mock_session):
    """リソースタイプからサービス名を取得するテスト"""
    collector = TestCollector(mock_session)
    
    # EC2関連のリソース
    assert collector.get_service_for_resource_type("aws_vpc") == "ec2"
    assert collector.get_service_for_resource_type("aws_subnet") == "ec2"
    assert collector.get_service_for_resource_type("aws_instance") == "ec2"
    assert collector.get_service_for_resource_type("aws_vpc_endpoint") == "ec2"
    
    # 他のサービスのリソース
    assert collector.get_service_for_resource_type("aws_s3_bucket") == "s3"
    assert collector.get_service_for_resource_type("aws_iam_role") == "iam"
    assert collector.get_service_for_resource_type("aws_lambda_function") == "lambda"
    
    # 無効なリソースタイプ
    assert collector.get_service_for_resource_type("invalid_type") == ""
    assert collector.get_service_for_resource_type("") == ""


def test_build_arn(mock_session):
    """ARN生成のテスト"""
    collector = TestCollector(mock_session)
    
    # S3バケット
    arn = collector.build_arn("bucket", "my-bucket")
    assert arn == "arn:aws:s3:::my-bucket"
    
    # IAMロール
    class IAMCollector(TestCollector):
        def get_service_name(self) -> str:
            return "iam"
    
    iam_collector = IAMCollector(mock_session)
    arn = iam_collector.build_arn("role", "my-role")
    assert arn == "arn:aws:iam::123456789012:role/my-role"
    
    # 通常のリソース
    arn = collector.build_arn("instance", "i-1234567890abcdef0")
    assert arn == f"arn:aws:ec2:ap-northeast-1:123456789012:instance/i-1234567890abcdef0"
