import json
import pytest
from unittest.mock import MagicMock
from terraform_aws_migrator.state_reader import TerraformStateReader
from tests.conftest import MockStreamingBody, MockClientError

def test_s3_state_handling(mock_session):
    """S3ステート処理のテスト"""
    reader = TerraformStateReader(mock_session)
    
    # S3クライアントのモックを設定
    s3_client = mock_session.client.return_value
    
    # テスト用のステートデータ
    state_data = {
        "version": 4,
        "terraform_version": "1.0.0",
        "serial": 1,
        "lineage": "test-lineage",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_vpc",
                "name": "main",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "vpc-12345678",
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
                            "tags": {
                                "Name": "TestVPC"
                            }
                        }
                    }
                ]
            }
        ]
    }
    
    # JSONデータを文字列にエンコード
    state_json = json.dumps(state_data, indent=2)
    # UTF-8でバイト列に変換
    encoded_state = state_json.encode('utf-8')
    
    # S3クライアントのモックを設定
    mock_body = MockStreamingBody(encoded_state)
    s3_client.get_object.return_value = {
        "Body": mock_body,
        "ContentLength": len(encoded_state),
        "ContentType": "application/json",
        "ResponseMetadata": {
            "HTTPStatusCode": 200
        }
    }
    s3_client.head_object.return_value = {
        "ContentLength": len(encoded_state),
        "ContentType": "application/json",
        "ResponseMetadata": {
            "HTTPStatusCode": 200
        }
    }

    # デバッグ用のログ出力
    print(f"Encoded state type: {type(encoded_state)}")
    print(f"Encoded state length: {len(encoded_state)}")
    print(f"Encoded state content: {encoded_state[:100]}")  # 最初の100バイトのみ表示
    
    # read()の結果を一度だけ取得して再利用
    read_result = mock_body.read()
    print(f"Mock body read result type: {type(read_result)}")
    print(f"Mock body read result: {read_result[:100]}")  # 最初の100バイトのみ表示
    
    # ストリームの位置をリセット
    mock_body.seek(0)
    
    # S3からのステート読み込みをテスト
    result = reader._get_s3_state("test-bucket", "test/terraform.tfstate", "ap-northeast-1")
    
    # 基本的な構造のテスト
    assert result is not None
    assert result["version"] == 4
    assert result["terraform_version"] == "1.0.0"
    assert result["serial"] == 1
    assert result["lineage"] == "test-lineage"
    
    # リソースの詳細なテスト
    assert "resources" in result
    assert len(result["resources"]) == 1
    resource = result["resources"][0]
    assert resource["type"] == "aws_vpc"
    assert resource["name"] == "main"
    assert resource["mode"] == "managed"
    
    # インスタンスの属性テスト
    instance = resource["instances"][0]
    assert instance["schema_version"] == 1
    assert instance["attributes"]["id"] == "vpc-12345678"
    assert instance["attributes"]["arn"] == "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678"
    assert instance["attributes"]["tags"] == {"Name": "TestVPC"}

def test_s3_state_handling_error_cases(mock_session):
    """S3ステート処理のエラーケースのテスト"""
    reader = TerraformStateReader(mock_session)
    s3_client = mock_session.client.return_value

    # 1. 無効なJSONの場合
    invalid_json = b"{"  # 不完全なJSON
    mock_body = MockStreamingBody(invalid_json)
    s3_client.get_object.return_value = {
        "Body": mock_body,
        "ContentLength": len(invalid_json),
        "ContentType": "application/json"
    }
    s3_client.head_object.return_value = {
        "ContentLength": len(invalid_json),
        "ContentType": "application/json"
    }
    
    result = reader._get_s3_state("test-bucket", "test/terraform.tfstate", "ap-northeast-1")
    assert result is None

    # 2. versionフィールドがない場合
    no_version_data = {
        "terraform_version": "1.0.0",
        "resources": []
    }
    mock_body = MockStreamingBody(json.dumps(no_version_data).encode('utf-8'))
    s3_client.get_object.return_value["Body"] = mock_body
    
    result = reader._get_s3_state("test-bucket", "test/terraform.tfstate", "ap-northeast-1")
    assert result is None

    # 3. resourcesフィールドがない場合
    no_resources_data = {
        "version": 4,
        "terraform_version": "1.0.0"
    }
    mock_body = MockStreamingBody(json.dumps(no_resources_data).encode('utf-8'))
    s3_client.get_object.return_value["Body"] = mock_body
    
    result = reader._get_s3_state("test-bucket", "test/terraform.tfstate", "ap-northeast-1")
    assert result is None

    # 4. S3オブジェクトが存在しない場合
    s3_client.head_object.side_effect = MockClientError("404", "Not Found")
    
    result = reader._get_s3_state("test-bucket", "test/terraform.tfstate", "ap-northeast-1")
    assert result is None
