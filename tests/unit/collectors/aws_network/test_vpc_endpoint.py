import pytest
import sys
import os

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from terraform_aws_migrator.auditor import AWSResourceAuditor
from terraform_aws_migrator.collectors.base import ResourceCollector, register_collector
import logging

logger = logging.getLogger(__name__)

def test_vpc_endpoint_identifier_generation_with_route_tables(mock_session):
    """VPCエンドポイントの識別子生成テスト（route_table_idsを含むケース）"""
    @register_collector
    class TestVpcEndpointCollector(ResourceCollector):
        def __init__(self, session=None):
            super().__init__(session)
            self._test_resources = [
                {
                    "type": "aws_vpc_endpoint",
                    "id": "dummy-vpce-1",
                    "arn": "",
                    "tags": [
                        {"Key": "Name", "Value": "dummy-front"}
                    ],
                    "details": {
                        "vpc_id": "dummy-vpc-1",
                        "service_name": "dummy-service",
                        "state": "available",
                        "vpc_endpoint_type": "Gateway",
                        "subnet_ids": [],
                        "route_table_ids": [],
                        "private_dns_enabled": False,
                        "network_interface_ids": [],
                        "dns_entries": [],
                        "policy": '{"Statement": [{"Action": "*", "Effect": "Allow", "Principal": "*", "Resource": "*"}], "Version": "2008-10-17"}',
                        "name": "dummy-front"
                    }
                },
                {
                    "type": "aws_vpc_endpoint",
                    "id": "dummy-vpce-2",
                    "arn": "",
                    "tags": [
                        {"Key": "Name", "Value": "dummy-back"}
                    ],
                    "details": {
                        "vpc_id": "dummy-vpc-2",
                        "service_name": "dummy-service",
                        "state": "available",
                        "vpc_endpoint_type": "Gateway",
                        "subnet_ids": [],
                        "route_table_ids": ["dummy-rtb"],
                        "private_dns_enabled": False,
                        "network_interface_ids": [],
                        "dns_entries": [],
                        "policy": '{"Statement": [{"Action": "*", "Effect": "Allow", "Principal": "*", "Resource": "*"}], "Version": "2008-10-17"}',
                        "name": "dummy-back"
                    }
                }
            ]

        def get_service_name(self) -> str:
            return "ec2"

        @classmethod
        def get_resource_types(cls) -> dict:
            return {
                "aws_vpc_endpoint": "VPC Endpoint"
            }

        def collect(self, target_resource_type: str = "") -> list:
            resources = self._test_resources.copy()
            if target_resource_type:
                return [r.copy() for r in resources if r["type"] == target_resource_type]
            return [r.copy() for r in resources]

        def generate_resource_identifier(self, resource: dict) -> str:
            """VPCエンドポイント用の識別子生成"""
            if resource.get("type") != "aws_vpc_endpoint":
                return super().generate_resource_identifier(resource)
            
            try:
                details = resource.get("details", {})
                vpc_id = details.get("vpc_id")
                service_name = details.get("service_name")
                endpoint_id = resource.get("id")
                name = details.get("name")

                # デバッグログを出力
                logger.debug(f"Generating identifier for VPC endpoint:")
                logger.debug(f"  vpc_id: {vpc_id}")
                logger.debug(f"  service_name: {service_name}")
                logger.debug(f"  endpoint_id: {endpoint_id}")
                logger.debug(f"  name: {name}")
                logger.debug(f"  details: {details}")

                # エンドポイントIDがある場合、そのIDを使って識別子生成
                if endpoint_id:
                    # 基本の識別子
                    identifier = f"{resource['type']}:{endpoint_id}"
                    
                    # 追加情報があれば詳細な識別子にする
                    if name and vpc_id and service_name:
                        identifier = f"{resource['type']}:{name}:{vpc_id}:{service_name}:{endpoint_id}"
                    elif vpc_id and service_name:
                        identifier = f"{resource['type']}:{vpc_id}:{service_name}:{endpoint_id}"
                    
                    logger.debug(f"Generated identifier: {identifier}")
                    return identifier

                logger.warning("Missing endpoint_id for VPC endpoint")
                return None

            except Exception as e:
                logger.error(f"Error generating identifier for VPC endpoint: {str(e)}")
                logger.debug(f"Resource: {resource}")
                return None

    from terraform_aws_migrator.collectors.base import registry
    registry.collectors = []
    register_collector(TestVpcEndpointCollector)

    auditor = AWSResourceAuditor()
    auditor.session = mock_session
    
    auditor.state_reader.get_managed_resources = lambda *args: {}
    
    result = auditor.audit_resources("dummy_tf_dir")
    
    ec2_resources = result["all_resources"].get("ec2", [])
    vpc_endpoints = [r for r in ec2_resources if r["type"] == "aws_vpc_endpoint"]
    assert len(vpc_endpoints) == 2  # 2件とも処理される

    front_endpoint = next(e for e in vpc_endpoints if e["id"] == "dummy-vpce-1")
    assert "identifier" in front_endpoint
    expected_front_identifier = "aws_vpc_endpoint:dummy-front:dummy-vpc-1:dummy-service:dummy-vpce-1"
    assert front_endpoint["identifier"] == expected_front_identifier

    back_endpoint = next(e for e in vpc_endpoints if e["id"] == "dummy-vpce-2")
    assert "identifier" in back_endpoint
    expected_back_identifier = "aws_vpc_endpoint:dummy-back:dummy-vpc-2:dummy-service:dummy-vpce-2"
    assert back_endpoint["identifier"] == expected_back_identifier

    assert back_endpoint["details"]["route_table_ids"] == ["dummy-rtb"]
    assert front_endpoint["details"]["route_table_ids"] == []
