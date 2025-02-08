import pytest
from terraform_aws_migrator.auditor import AWSResourceAuditor
from terraform_aws_migrator.collectors.base import ResourceCollector, register_collector


@pytest.fixture
def mock_collector(mock_session):
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


def test_resource_matching(mock_session, sample_state_data, mock_collector):
    """リソースの照合と管理状態の判定テスト"""
    auditor = AWSResourceAuditor()
    auditor.session = mock_session
    
    # リソースの監査を実行
    result = auditor.audit_resources("dummy_tf_dir")
    
    # EC2サービスのリソースを確認
    ec2_resources = result["all_resources"].get("ec2", [])
    assert len(ec2_resources) == 2
    
    # VPCリソースの確認
    vpc = next(r for r in ec2_resources if r["type"] == "aws_vpc")
    assert vpc["id"] == "vpc-12345678"
    assert vpc["managed"] is False  # 未管理状態の確認
    
    # サブネットリソースの確認
    subnet = next(r for r in ec2_resources if r["type"] == "aws_subnet")
    assert subnet["id"] == "subnet-12345678"
    assert subnet["managed"] is False


def test_identifier_based_mapping(mock_session, mock_collector):
    """識別子を使用したリソースのマッピングテスト"""
    auditor = AWSResourceAuditor()
    auditor.session = mock_session
    
    # 既存の管理されたリソース
    managed_resources = {
        "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678": {
            "type": "aws_vpc",
            "id": "vpc-12345678",
            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
            "managed": True
        }
    }
    
    # モックのstate_reader
    auditor.state_reader.get_managed_resources = lambda *args: managed_resources
    
    # リソースの監査を実行
    result = auditor.audit_resources("dummy_tf_dir")
    
    # EC2サービスのリソースを確認
    ec2_resources = result["all_resources"].get("ec2", [])
    
    # VPCリソースの確認（管理状態）
    vpc = next(r for r in ec2_resources if r["type"] == "aws_vpc")
    assert vpc["managed"] is True
    
    # サブネットリソースの確認（未管理状態）
    subnet = next(r for r in ec2_resources if r["type"] == "aws_subnet")
    assert subnet["managed"] is False


def test_resource_exclusion(mock_session, mock_collector):
    """リソース除外設定のテスト"""
    # 除外設定付きでAuditorを初期化
    auditor = AWSResourceAuditor(exclusion_file="dummy_ignore_file")
    auditor.session = mock_session
    
    # 除外設定をモック
    auditor.exclusion_config.should_exclude = lambda resource: resource["type"] == "aws_vpc"
    
    # リソースの監査を実行
    result = auditor.audit_resources("dummy_tf_dir")
    
    # EC2サービスのリソースを確認
    ec2_resources = result["all_resources"].get("ec2", [])
    
    # VPCが除外され、サブネットのみが含まれていることを確認
    assert len(ec2_resources) == 1
    assert ec2_resources[0]["type"] == "aws_subnet"


def test_service_type_mapping(mock_session, mock_collector):
    """サービス名とリソースタイプのマッピングテスト"""
    auditor = AWSResourceAuditor(target_resource_type="aws_vpc")
    auditor.session = mock_session
    
    # リソースの監査を実行
    result = auditor.audit_resources("dummy_tf_dir")
    
    # 特定のリソースタイプのみが含まれていることを確認
    ec2_resources = result["all_resources"].get("ec2", [])
    resource_types = {r["type"] for r in ec2_resources}
    assert resource_types == {"aws_vpc"}


def test_resource_details_preservation(mock_session, mock_collector):
    """リソース詳細情報の保持テスト"""
    auditor = AWSResourceAuditor()
    auditor.session = mock_session
    
    # リソースの監査を実行
    result = auditor.audit_resources("dummy_tf_dir")
    
    # EC2サービスのリソースを確認
    ec2_resources = result["all_resources"].get("ec2", [])
    
    # VPCリソースの詳細情報を確認
    vpc = next(r for r in ec2_resources if r["type"] == "aws_vpc")
    assert "details" in vpc
    assert vpc["details"]["cidr_block"] == "10.0.0.0/16"
    
    # サブネットリソースの詳細情報を確認
    subnet = next(r for r in ec2_resources if r["type"] == "aws_subnet")
    assert "details" in subnet
    assert subnet["details"]["vpc_id"] == "vpc-12345678"
    assert subnet["details"]["cidr_block"] == "10.0.1.0/24"


def test_managed_resource_count(mock_session, mock_collector):
    """マネージドリソースのカウントテスト"""
    auditor = AWSResourceAuditor()
    auditor.session = mock_session
    
    # 既存の管理されたリソース（より複雑なケース）
    managed_resources = {
        # 通常のリソース
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
        },
        # モジュールリソース
        "arn:aws:dynamodb:ap-northeast-1:123456789012:table/test-table": {
            "type": "module.fa_common_modules_stag.aws_dynamodb_table",
            "id": "test-table",
            "arn": "arn:aws:dynamodb:ap-northeast-1:123456789012:table/test-table",
            "managed": True
        },
        "arn:aws:ec2:ap-northeast-1:123456789012:instance/i-1234567890abcdef0": {
            "type": "module.fa_common_modules_stag.aws_instance",
            "id": "i-1234567890abcdef0",
            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:instance/i-1234567890abcdef0",
            "managed": True
        },
        # IAM Role with path-based identifier
        "arn:aws:iam::123456789012:role/service-role/test-role": {
            "type": "aws_iam_role",
            "id": "test-role",
            "arn": "arn:aws:iam::123456789012:role/service-role/test-role",
            "managed": True
        },
        # S3 Bucket with name-based identifier
        "aws_s3_bucket:my-test-bucket": {
            "type": "aws_s3_bucket",
            "id": "my-test-bucket",
            "managed": True
        }
    }
    
    # モックのstate_reader
    auditor.state_reader.get_managed_resources = lambda *args: managed_resources
    
    # コレクターを作成
    @register_collector
    class TestCollector(ResourceCollector):
        def __init__(self, session=None):
            super().__init__(session)
            self._current_service = "ec2"
            self._test_resources = []
            self.set_service("ec2")

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

        def collect(self, target_resource_type: str = "") -> list:
            resources = self._test_resources.copy()
            if target_resource_type:
                return [r.copy() for r in resources if r["type"] == target_resource_type]
            return [r.copy() for r in resources]

        @classmethod
        def get_resource_types(cls) -> dict:
            return {
                "aws_vpc": "VPC",
                "aws_subnet": "Subnet",
                "aws_iam_role": "IAM Role",
                "aws_s3_bucket": "S3 Bucket"
            }

        @classmethod
        def get_service_for_resource_type(cls, resource_type: str) -> str:
            if resource_type.startswith("aws_vpc") or resource_type.startswith("aws_subnet"):
                return "ec2"
            elif resource_type.startswith("aws_iam"):
                return "iam"
            elif resource_type.startswith("aws_s3"):
                return "s3"
            return ""

    collector = TestCollector(mock_session)
    auditor._get_relevant_collectors = lambda: [collector]

    # EC2リソースの監査
    collector.set_service("ec2")
    result_ec2 = auditor.audit_resources("dummy_tf_dir")
    ec2_resources = result_ec2["all_resources"].get("ec2", [])

    # IAMリソースの監査
    collector.set_service("iam")
    result_iam = auditor.audit_resources("dummy_tf_dir")
    iam_resources = result_iam["all_resources"].get("iam", [])

    # S3リソースの監査
    collector.set_service("s3")
    result_s3 = auditor.audit_resources("dummy_tf_dir")
    s3_resources = result_s3["all_resources"].get("s3", [])

    # マネージドリソースの数を確認
    managed_count = (
        sum(1 for r in ec2_resources if r.get("managed", False)) +
        sum(1 for r in iam_resources if r.get("managed", False)) +
        sum(1 for r in s3_resources if r.get("managed", False))
    )
    assert managed_count == 4
    
    # 各リソースタイプごとのマネージド数を確認
    vpc_managed = sum(1 for r in ec2_resources if r["type"] == "aws_vpc" and r.get("managed", False))
    subnet_managed = sum(1 for r in ec2_resources if r["type"] == "aws_subnet" and r.get("managed", False))
    role_managed = sum(1 for r in iam_resources if r["type"] == "aws_iam_role" and r.get("managed", False))
    bucket_managed = sum(1 for r in s3_resources if r["type"] == "aws_s3_bucket" and r.get("managed", False))
    
    assert vpc_managed == 1
    assert subnet_managed == 1
    assert role_managed == 1
    assert bucket_managed == 1


def test_complex_resource_matching(mock_session):
    """複雑なリソースマッチングのテスト"""
    @register_collector
    class ComplexTestCollector(ResourceCollector):
        def __init__(self, session=None):
            super().__init__(session)
            self._current_service = "ec2"
            self._test_resources = []
            self.set_service("ec2")

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
                        "type": "module.fa_common_modules_stag.aws_instance",
                        "id": "i-1234567890abcdef0",
                        "arn": "arn:aws:ec2:ap-northeast-1:123456789012:instance/i-1234567890abcdef0",
                        "tags": [{"Key": "Name", "Value": "ModuleInstance"}],
                        "details": {"instance_type": "t3.micro"}
                    }
                ]
            elif service == "dynamodb":
                self._test_resources = [{
                    "type": "module.fa_common_modules_stag.aws_dynamodb_table",
                    "id": "test-table",
                    "arn": "arn:aws:dynamodb:ap-northeast-1:123456789012:table/test-table",
                    "tags": [{"Key": "Environment", "Value": "Staging"}],
                    "details": {"billing_mode": "PAY_PER_REQUEST"}
                }]
            elif service == "iam":
                self._test_resources = [{
                    "type": "aws_iam_role",
                    "id": "test-role",
                    "arn": "arn:aws:iam::123456789012:role/service-role/test-role",
                    "path": "/service-role/",
                    "tags": [{"Key": "Service", "Value": "Lambda"}]
                }]
            elif service == "s3":
                self._test_resources = [{
                    "type": "aws_s3_bucket",
                    "id": "my-test-bucket",
                    "arn": "arn:aws:s3:::my-test-bucket",
                    "tags": [{"Key": "Environment", "Value": "Test"}]
                }]

        @classmethod
        def get_resource_types(cls) -> dict:
            return {
                "aws_vpc": "VPC",
                "module.fa_common_modules_stag.aws_instance": "EC2 Instance (Module)",
                "module.fa_common_modules_stag.aws_dynamodb_table": "DynamoDB Table (Module)",
                "aws_iam_role": "IAM Role",
                "aws_s3_bucket": "S3 Bucket"
            }

        def collect(self, target_resource_type: str = "") -> list:
            resources = self._test_resources.copy()
            if target_resource_type:
                return [r.copy() for r in resources if r["type"] == target_resource_type]
            return [r.copy() for r in resources]

        @classmethod
        def get_service_for_resource_type(cls, resource_type: str) -> str:
            if resource_type.startswith("aws_vpc") or "aws_instance" in resource_type:
                return "ec2"
            elif "aws_dynamodb_table" in resource_type:
                return "dynamodb"
            elif resource_type.startswith("aws_iam"):
                return "iam"
            elif resource_type.startswith("aws_s3"):
                return "s3"
            return ""

    auditor = AWSResourceAuditor()
    auditor.session = mock_session

    # 既存の管理されたリソース
    managed_resources = {
        # 通常のリソース
        "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678": {
            "type": "aws_vpc",
            "id": "vpc-12345678",
            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
            "managed": True
        },
        # モジュールリソース
        "arn:aws:ec2:ap-northeast-1:123456789012:instance/i-1234567890abcdef0": {
            "type": "module.fa_common_modules_stag.aws_instance",
            "id": "i-1234567890abcdef0",
            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:instance/i-1234567890abcdef0",
            "managed": True
        },
        "arn:aws:dynamodb:ap-northeast-1:123456789012:table/test-table": {
            "type": "module.fa_common_modules_stag.aws_dynamodb_table",
            "id": "test-table",
            "arn": "arn:aws:dynamodb:ap-northeast-1:123456789012:table/test-table",
            "managed": True
        }
    }

    # モックのstate_reader
    auditor.state_reader.get_managed_resources = lambda *args: managed_resources

    # コレクターを作成
    collector = ComplexTestCollector(mock_session)
    auditor._get_relevant_collectors = lambda: [collector]

    # EC2リソースの監査（通常のリソースとモジュールリソース）
    collector.set_service("ec2")
    result_ec2 = auditor.audit_resources("dummy_tf_dir")
    ec2_resources = result_ec2["all_resources"].get("ec2", [])
    
    # 通常のVPCリソースの確認
    assert any(r["type"] == "aws_vpc" for r in ec2_resources)
    vpc = next(r for r in ec2_resources if r["type"] == "aws_vpc")
    assert vpc["managed"] is True

    # モジュールのEC2インスタンスリソースの確認
    assert any("aws_instance" in r["type"] for r in ec2_resources)
    instance = next(r for r in ec2_resources if "aws_instance" in r["type"])
    assert instance["managed"] is True
    assert instance["type"] == "module.fa_common_modules_stag.aws_instance"

    # DynamoDBリソースの監査（モジュールリソース）
    collector.set_service("dynamodb")
    result_dynamodb = auditor.audit_resources("dummy_tf_dir")
    dynamodb_resources = result_dynamodb["all_resources"].get("dynamodb", [])
    assert any("aws_dynamodb_table" in r["type"] for r in dynamodb_resources)
    table = next(r for r in dynamodb_resources if "aws_dynamodb_table" in r["type"])
    assert table["managed"] is True
    assert table["type"] == "module.fa_common_modules_stag.aws_dynamodb_table"

    # IAMリソースの監査（未管理リソース）
    collector.set_service("iam")
    result_iam = auditor.audit_resources("dummy_tf_dir")
    iam_resources = result_iam["all_resources"].get("iam", [])
    assert any(r["type"] == "aws_iam_role" for r in iam_resources)
    role = next(r for r in iam_resources if r["type"] == "aws_iam_role")
    assert role["managed"] is False

    # S3リソースの監査（未管理リソース）
    collector.set_service("s3")
    result_s3 = auditor.audit_resources("dummy_tf_dir")
    s3_resources = result_s3["all_resources"].get("s3", [])
    assert any(r["type"] == "aws_s3_bucket" for r in s3_resources)
    bucket = next(r for r in s3_resources if r["type"] == "aws_s3_bucket")
    assert bucket["managed"] is False


def test_real_state_file(mock_session):
    """実際のTerraformステートファイルを使用したテスト"""
    auditor = AWSResourceAuditor()
    auditor.session = mock_session

    # テストフィクスチャのディレクトリを使用
    result = auditor.audit_resources("tests/fixtures")

    # 結果の検証
    all_resources = result["all_resources"]
    assert len(all_resources) > 0

    # マネージドリソースの存在を確認
    managed_count = sum(1 for resources in all_resources.values()
                       for r in resources if r.get("managed", False))
    assert managed_count > 0

    # 特定のリソースタイプの確認
    ec2_resources = all_resources.get("ec2", [])
    vpc_resources = [r for r in ec2_resources if r["type"] == "aws_vpc"]
    assert len(vpc_resources) > 0
    assert any(r["managed"] for r in vpc_resources)
    
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
    
    # EC2サービスのリソースを確認
    ec2_resources = result["all_resources"].get("ec2", [])
    
    # マネージドリソースの数を確認
    managed_count = sum(1 for r in ec2_resources if r.get("managed", False))
    assert managed_count == 2
    
    # 各リソースタイプごとのマネージド数を確認
    vpc_managed = sum(1 for r in ec2_resources if r["type"] == "aws_vpc" and r.get("managed", False))
    subnet_managed = sum(1 for r in ec2_resources if r["type"] == "aws_subnet" and r.get("managed", False))
    
    assert vpc_managed == 1
    assert subnet_managed == 1
