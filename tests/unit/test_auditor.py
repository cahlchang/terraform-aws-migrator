import pytest
from terraform_aws_migrator.auditor import AWSResourceAuditor
from terraform_aws_migrator.collectors.base import ResourceCollector, register_collector


@pytest.fixture
def mock_collector():
    """テスト用のモックコレクター"""
    @register_collector
    class TestCollector(ResourceCollector):
        def __init__(self, session=None):
            super().__init__(session)
            self._current_service = "ec2"
            self._test_resources = [
                {
                    "type": "aws_vpc",
                    "id": "vpc-12345678",
                    "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
                    "tags": [{"Key": "Name", "Value": "MainVPC"}],
                    "details": {"cidr_block": "10.0.0.0/16"}
                },
                {
                    "type": "aws_subnet",
                    "id": "subnet-12345678",
                    "arn": "arn:aws:ec2:ap-northeast-1:123456789012:subnet/subnet-12345678",
                    "tags": [{"Key": "Name", "Value": "PublicSubnet"}],
                    "details": {
                        "vpc_id": "vpc-12345678",
                        "cidr_block": "10.0.1.0/24"
                    }
                }
            ]

        def get_service_name(self) -> str:
            return self._current_service

        def set_service(self, service: str):
            self._current_service = service
            if service == "ec2":
                self._test_resources = [
                    {
                        "type": "aws_vpc",
                        "id": "vpc-12345678",
                        "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
                        "tags": [{"Key": "Name", "Value": "MainVPC"}],
                        "details": {"cidr_block": "10.0.0.0/16"}
                    },
                    {
                        "type": "aws_subnet",
                        "id": "subnet-12345678",
                        "arn": "arn:aws:ec2:ap-northeast-1:123456789012:subnet/subnet-12345678",
                        "tags": [{"Key": "Name", "Value": "PublicSubnet"}],
                        "details": {
                            "vpc_id": "vpc-12345678",
                            "cidr_block": "10.0.1.0/24"
                        }
                    }
                ]
            elif service == "iam":
                self._test_resources = [
                    {
                        "type": "aws_iam_role",
                        "id": "test-role",
                        "arn": "arn:aws:iam::123456789012:role/service-role/test-role",
                        "path": "/service-role/",
                        "tags": [{"Key": "Service", "Value": "Lambda"}]
                    }
                ]
            elif service == "s3":
                self._test_resources = [
                    {
                        "type": "aws_s3_bucket",
                        "id": "my-test-bucket",
                        "arn": "arn:aws:s3:::my-test-bucket",
                        "tags": [{"Key": "Environment", "Value": "Test"}]
                    }
                ]
            
        @classmethod
        def get_resource_types(cls) -> dict:
            return {
                "aws_vpc": "VPC",
                "aws_subnet": "Subnet"
            }
            
        def collect(self, target_resource_type: str = "") -> list:
            resources = self._test_resources.copy()
            if target_resource_type:
                return [r.copy() for r in resources if r["type"] == target_resource_type]
            return [r.copy() for r in resources]

        def generate_resource_identifier(self, resource: dict) -> str:
            """リソース識別子の生成"""
            resource_type = resource.get("type", "")
            resource_id = resource.get("id", "")
            
            # ARNがある場合はそれを使用
            if "arn" in resource:
                return resource["arn"]
                
            # リソースタイプに基づいて識別子を生成
            if resource_type == "aws_vpc":
                return f"aws_vpc:{resource_id}"
            elif resource_type == "aws_subnet":
                return f"aws_subnet:{resource_id}"
            elif resource_type and resource_id:
                return f"{resource_type}:{resource_id}"
                
            # フォールバック：空の文字列を返す
            return ""
    
    return TestCollector


def test_real_state_file_managed(mock_session, mock_collector):
    """実際のTerraformステートファイルを使用したテスト（マネージドリソース）"""
    auditor = AWSResourceAuditor()
    auditor.session = mock_session

    # モックコレクターを設定
    collector = mock_collector(mock_session)
    auditor._get_relevant_collectors = lambda: [collector]
    
    # 既存の管理されたリソース
    managed_resources = {
        "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678": {
            "type": "aws_vpc",
            "id": "vpc-12345678",
            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
            "managed": True
        },
        "aws_subnet:subnet-12345678": {
            "type": "aws_subnet",
            "id": "subnet-12345678",
            "managed": True
        }
    }
    
    # モックのstate_reader
    auditor.state_reader.get_managed_resources = lambda *args: managed_resources
    
    # リソースの監査を実行
    result = auditor.audit_resources("dummy_tf_dir")
    
    # EC2サービスのリソースを確認（VPCとサブネットのみ）
    ec2_resources = [r for r in result["all_resources"].get("ec2", [])
                    if r["type"] in ["aws_vpc", "aws_subnet"]]
    
    # マネージドリソースの数を確認
    managed_count = sum(1 for r in ec2_resources if r.get("managed", False))
    assert managed_count == 2
    
    # 各リソースタイプごとのマネージド数を確認
    vpc_managed = sum(1 for r in ec2_resources if r["type"] == "aws_vpc" and r.get("managed", False))
    subnet_managed = sum(1 for r in ec2_resources if r["type"] == "aws_subnet" and r.get("managed", False))
    
    assert vpc_managed == 1
    assert subnet_managed == 1
