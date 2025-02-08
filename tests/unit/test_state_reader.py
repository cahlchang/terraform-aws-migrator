import pytest
from unittest.mock import MagicMock
from terraform_aws_migrator.state_reader import TerraformStateReader
from pathlib import Path
import json
import json
import tempfile
import os
import io
import json


def test_get_identifier_for_managed_set(mock_session):
    """リソース識別子の生成テスト"""
    reader = TerraformStateReader(mock_session)
    
    # ARNを持つリソース
    resource_with_arn = {
        "type": "aws_vpc",
        "id": "vpc-12345678",
        "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
        "tags": [{"Key": "Name", "Value": "MainVPC"}]
    }
    identifier = reader._get_identifier_for_managed_set(resource_with_arn)
    assert identifier == "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    
    # IAMロールポリシーアタッチメント
    role_policy_attachment = {
        "type": "aws_iam_role_policy_attachment",
        "role": "test-role",
        "policy_arn": "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    }
    identifier = reader._get_identifier_for_managed_set(role_policy_attachment)
    assert identifier == f"arn:aws:iam::{mock_session.client('sts').get_caller_identity()['Account']}:role/test-role/arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
    
    # 通常のリソース（ARNなし）
    normal_resource = {
        "type": "aws_security_group",
        "id": "sg-12345678",
        "tags": [{"Key": "Name", "Value": "WebServerSG"}]
    }
    identifier = reader._get_identifier_for_managed_set(normal_resource)
    assert identifier == "aws_security_group:sg-12345678"


def test_extract_resources_from_state(mock_session, sample_state_data):
    """stateファイルからのリソース抽出テスト"""
    reader = TerraformStateReader(mock_session)
    managed_resources = {}
    
    reader._extract_resources_from_state(sample_state_data, managed_resources)
    
    # VPCリソースの検証
    vpc_identifier = "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    assert vpc_identifier in managed_resources
    vpc = managed_resources[vpc_identifier]
    assert vpc["type"] == "aws_vpc"
    assert vpc["id"] == "vpc-12345678"
    assert vpc["details"]["cidr_block"] == "10.0.0.0/16"
    
    # サブネットリソースの検証
    subnet_identifier = "aws_subnet:subnet-12345678"
    assert subnet_identifier in managed_resources
    subnet = managed_resources[subnet_identifier]
    assert subnet["type"] == "aws_subnet"
    assert subnet["id"] == "subnet-12345678"
    assert subnet["details"]["vpc_id"] == "vpc-12345678"


def test_duplicate_resource_handling(mock_session):
    """重複リソースの処理テスト"""
    reader = TerraformStateReader(mock_session)
    managed_resources = {}
    
    # 重複するリソースを含むステートデータ
    duplicate_state = {
        "version": 4,
        "resources": [
            {
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-12345678",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
                        }
                    }
                ]
            },
            {
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main_duplicate",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-12345678",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
                        }
                    }
                ]
            }
        ]
    }
    
    reader._extract_resources_from_state(duplicate_state, managed_resources)
    
    # 同じARNを持つリソースは1つだけ保持されているか確認
    vpc_resources = [r for r in managed_resources.values() if r["type"] == "aws_vpc"]
    assert len(vpc_resources) == 1


def test_module_resource_handling(mock_session):
    """モジュール内のリソース処理テスト"""
    reader = TerraformStateReader(mock_session)
    managed_resources = {}
    
    # モジュール内のリソースを含むステートデータ
    module_state = {
        "version": 4,
        "resources": [
            {
                "module": "module.network",
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-12345678",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
                        }
                    }
                ]
            }
        ]
    }
    
    reader._extract_resources_from_state(module_state, managed_resources)
    
    # モジュールパスが含まれていないことを確認
    vpc_resources = [r for r in managed_resources.values() if r["type"] == "aws_vpc"]
    assert len(vpc_resources) == 1
    assert vpc_resources[0]["type"] == "aws_vpc"


def test_tag_handling(mock_session):
    """タグの処理テスト"""
    reader = TerraformStateReader(mock_session)
    managed_resources = {}
    
    # 異なる形式のタグを含むステートデータ
    tag_state = {
        "version": 4,
        "resources": [
            {
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-12345678",
                            "tags": {
                                "Name": "MainVPC",
                                "Environment": "Production"
                            }
                        }
                    }
                ]
            },
            {
                "mode": "managed",
                "type": "aws_subnet",
                "name": "public",
                "instances": [
                    {
                        "attributes": {
                            "id": "subnet-12345678",
                            "tags": [
                                {"Key": "Name", "Value": "PublicSubnet"}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    reader._extract_resources_from_state(tag_state, managed_resources)
    
    # 異なる形式のタグが正しく処理されているか確認
    vpc = next(r for r in managed_resources.values() if r["type"] == "aws_vpc")
    subnet = next(r for r in managed_resources.values() if r["type"] == "aws_subnet")
    
    assert isinstance(vpc["tags"], list)
    assert isinstance(subnet["tags"], list)
    assert {"Key": "Name", "Value": "MainVPC"} in vpc["tags"]
    assert {"Key": "Name", "Value": "PublicSubnet"} in subnet["tags"]


def test_resource_mode_handling(mock_session):
    """リソースのモード処理テスト"""
    reader = TerraformStateReader(mock_session)
    managed_resources = {}
    
    # 異なるモードのリソースを含むステートデータ
    mode_state = {
        "version": 4,
        "resources": [
            {
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-12345678",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
                        }
                    }
                ]
            },
            {
                "mode": "data",
                "type": "aws_vpc",
                "name": "existing",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-87654321",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-87654321"
                        }
                    }
                ]
            },
            {
                "type": "aws_subnet",  # モードなし
                "name": "public",
                "instances": [
                    {
                        "attributes": {
                            "id": "subnet-12345678",
                            "vpc_id": "vpc-12345678"
                        }
                    }
                ]
            }
        ]
    }
    
    reader._extract_resources_from_state(mode_state, managed_resources)
    
    # managedモードのリソースのみが含まれているか確認
    assert len(managed_resources) == 1
    vpc = next(r for r in managed_resources.values() if r["type"] == "aws_vpc")
    assert vpc["id"] == "vpc-12345678"

    # dataモードとモードなしのリソースが除外されているか確認
    data_vpc = next((r for r in managed_resources.values() if r.get("id") == "vpc-87654321"), None)
    assert data_vpc is None
    subnet = next((r for r in managed_resources.values() if r["type"] == "aws_subnet"), None)
    assert subnet is None


def test_get_managed_resources_local_state(mock_session, tmp_path):
    """ローカルtfstateファイルからのリソース読み込みテスト"""
    reader = TerraformStateReader(mock_session)
    
    # テスト用のtfstateファイルを作成
    state_data = {
        "version": 4,
        "resources": [
            {
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main",
                "instances": [
                    {
                        "attributes": {
                            "id": "vpc-12345678",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
                            "cidr_block": "10.0.0.0/16"
                        }
                    }
                ]
            }
        ]
    }
    
    tf_dir = tmp_path / "terraform"
    tf_dir.mkdir()
    state_file = tf_dir / "terraform.tfstate"
    state_file.write_text(json.dumps(state_data))
    
    # リソースの取得
    managed_resources = reader.get_managed_resources(str(tf_dir))
    
    # 結果の検証
    assert len(managed_resources) == 1
    vpc_identifier = "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    assert vpc_identifier in managed_resources
    vpc = managed_resources[vpc_identifier]
    assert vpc["type"] == "aws_vpc"
    assert vpc["id"] == "vpc-12345678"
    assert vpc["details"]["cidr_block"] == "10.0.0.0/16"


def test_get_managed_resources_from_fixture(mock_session):
    """テストフィクスチャからのマネージドリソース読み込みテスト"""
    reader = TerraformStateReader(mock_session)
    
    # テストフィクスチャのディレクトリを取得
    fixture_dir = Path(__file__).parent.parent / "fixtures"
    
    # マネージドリソースの取得
    managed_resources = reader.get_managed_resources(str(fixture_dir))
    
    # 結果の検証
    assert len(managed_resources) == 5  # VPC, 2 Load Balancers, Subnet, IAM Role
    
    # VPCリソースの検証
    vpc_identifier = "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    assert vpc_identifier in managed_resources
    vpc = managed_resources[vpc_identifier]
    assert vpc["type"] == "aws_vpc"
    assert vpc["id"] == "vpc-12345678"
    assert vpc["details"]["cidr_block"] == "10.0.0.0/16"
    assert vpc["details"]["enable_dns_hostnames"] is True
    
    # サブネットリソースの検証
    subnet_identifier = "aws_subnet:subnet-12345678"
    assert subnet_identifier in managed_resources
    subnet = managed_resources[subnet_identifier]
    assert subnet["type"] == "aws_subnet"
    assert subnet["id"] == "subnet-12345678"
    assert subnet["details"]["vpc_id"] == "vpc-12345678"
    assert subnet["details"]["cidr_block"] == "10.0.1.0/24"
    
    # IAMロールリソースの検証
    role_identifier = "arn:aws:iam::123456789012:role/test-role"
    assert role_identifier in managed_resources
    role = managed_resources[role_identifier]
    assert role["type"] == "aws_iam_role"
    assert role["id"] == "test-role"
    assert role["details"]["path"] == "/"
    assert "assume_role_policy" in role["details"]

# def test_get_managed_resources_s3_backend(mock_session, tmp_path):
#     """S3バックエンドからのリソース読み込みテスト"""
#     reader = TerraformStateReader(mock_session)
    
#     # テスト用のTerraformバックエンド設定ファイルを作成
#     tf_dir = tmp_path / "terraform"
#     tf_dir.mkdir()
#     backend_file = tf_dir / "main.tf"
#     backend_file.write_text("""
# terraform {
#   backend "s3" {
#     bucket = "test-bucket"
#     key    = "test/terraform.tfstate"
#     region = "ap-northeast-1"
#   }
# }
# """)

#     # テスト用のステートデータを定義
#     state_data = {
#         "version": 4,
#         "resources": [
#             {
#                 "mode": "managed",
#                 "type": "aws_vpc",
#                 "name": "main",
#                 "instances": [
#                     {
#                         "attributes": {
#                             "id": "vpc-12345678",
#                             "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
#                             "cidr_block": "10.0.0.0/16"
#                         }
#                     }
#                 ]
#             }
#         ]
#     }

#     # モックレスポンスの準備
#     encoded_state = json.dumps(state_data).encode('utf-8')
#     print(f"Encoded state (bytes): {encoded_state}")
#     print(f"Decoded state: {encoded_state.decode('utf-8')}")

#     # get_objectのモック設定
#     mock_body = MagicMock()
#     mock_reads = []  # 読み取りの履歴を保存
#     def mock_read():
#         result = encoded_state
#         mock_reads.append(result)
#         print(f"[DEBUG] mock_read called, returning: {result[:100]}")
#         return result
#     mock_body.read = mock_read
    
#     def mock_get_object(**kwargs):
#         print(f"[DEBUG] get_object called with args: {kwargs}")
#         return {"Body": mock_body}
#     s3_client.get_object = MagicMock(side_effect=mock_get_object)
#     print("[DEBUG] Configured get_object mock")

#     # head_objectのモック設定
#     def mock_head_object(**kwargs):
#         print(f"[DEBUG] head_object called with args: {kwargs}")
#         return {"ContentLength": len(encoded_state)}
#     s3_client.head_object = MagicMock(side_effect=mock_head_object)
#     print("[DEBUG] Configured head_object mock")

#     # 例外クラスのモック
#     class MockClientError(Exception):
#         def __init__(self, error_response):
#             self.response = error_response
#     s3_client.exceptions.ClientError = MockClientError
#     print("[DEBUG] Configured ClientError mock")

#     # バックエンド設定のモック
#     mock_backend_config = {
#         "bucket": "test-bucket",
#         "key": "test/terraform.tfstate",
#         "region": "ap-northeast-1"
#     }
#     reader._find_s3_backend = MagicMock(return_value=mock_backend_config)
#     print("[DEBUG] Configured backend mock")

#     print("[DEBUG] About to call get_managed_resources")
#     managed_resources = reader.get_managed_resources(str(tf_dir))
    
#     print(f"[DEBUG] Number of mock_read calls: {len(mock_reads)}")
#     for i, data in enumerate(mock_reads):
#         print(f"[DEBUG] mock_read call {i} returned: {data[:100]}")

#     assert len(managed_resources) == 1
