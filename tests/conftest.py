import pytest
from unittest.mock import MagicMock
from pathlib import Path
from terraform_aws_migrator.collectors.aws_network.network import LoadBalancerV2Collector

@pytest.fixture
def mock_session():
    # モックされたセッションオブジェクトを作成
    mock = MagicMock()
    mock.region_name = "ap-northeast-1"
    mock.account_id = "123456789012"  # 例として固定のアカウントIDを設定

    # STSクライアントのモックを作成
    sts_client = MagicMock()
    sts_client.get_caller_identity.return_value = {"Account": mock.account_id}

    # セッションのクライアントメソッドが適切なクライアントを返すように設定
    def get_client(service_name, *args, **kwargs):
        if service_name == 'sts':
            return sts_client
        return MagicMock()
    
    mock.client.side_effect = get_client

    return mock

@pytest.fixture
def sample_state_data():
    # サンプルの状態データを提供
    sample_data = {
        "version": 4,
        "terraform_version": "1.5.7",
        "serial": 2,
        "lineage": "sample-lineage",
        "outputs": {},
        "resources": [
            {
                "module": "module.sample_module",
                "mode": "managed",
                "type": "aws_vpc",
                "name": "sample_vpc",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 0,
                        "attributes": {
                            "arn": "arn:aws:ec2:ap-northeast-1:123456789012:vpc/vpc-12345678",
                            "cidr_block": "10.0.0.0/16",
                            "is_default": False,
                            "id": "vpc-12345678",
                            "tags": {},
                            "tags_all": {}
                        }
                    }
                ]
            },
            {
                "module": "module.sample_module",
                "mode": "managed",
                "type": "aws_lb",
                "name": "sample_lb",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 0,
                        "attributes": {
                            "arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/sample-lb/abcdef123456",
                            "id": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/sample-lb/abcdef123456",
                            "name": "sample-lb",
                            "load_balancer_type": "application",
                            "subnets": ["subnet-aaaa1111", "subnet-bbbb2222"],
                            "security_groups": ["sg-aaaa1111"],
                            "vpc_id": "vpc-12345678",
                            "tags": {},
                            "tags_all": {}
                        }
                    }
                ]
            },
            {
                "module": "module.sample_module",
                "mode": "managed",
                "type": "aws_lb",
                "name": "test-lb",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 0,
                        "attributes": {
                            "arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890",
                            "id": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890",
                            "name": "test-lb",
                            "load_balancer_type": "application",
                            "subnets": ["subnet-33333333", "subnet-44444444"],
                            "security_groups": ["sg-87654321"],
                            "vpc_id": "vpc-87654321",
                            "tags": {},
                            "tags_all": {}
                        }
                    }
                ]
            },
            {
                "module": "module.sample_module",
                "mode": "managed",
                "type": "aws_subnet",
                "name": "sample_subnet",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 0,
                        "attributes": {
                            "id": "subnet-12345678",
                            "vpc_id": "vpc-12345678",
                            "cidr_block": "10.0.1.0/24",
                            "availability_zone": "ap-northeast-1a",
                            "tags": {},
                            "tags_all": {}
                        }
                    }
                ]
            }
        ]
    }
    return sample_data

@pytest.fixture
def mock_collector(mock_session):
    """LoadBalancerV2Collectorのモックを提供するフィクスチャ"""
    collector = LoadBalancerV2Collector(mock_session)
    
    # ELBv2クライアントのモックを取得
    elbv2_client = mock_session.client('elbv2')
    
    # describe_load_balancersのモックレスポンスを設定
    paginator = MagicMock()
    paginator.paginate.return_value = [{
        "LoadBalancers": [
            {
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890",
                "LoadBalancerName": "test-lb",
                "Type": "application",  # ALBのみを収集
                "Scheme": "internet-facing",
                "VpcId": "vpc-12345678",
                "State": {"Code": "active"},
                "AvailabilityZones": [
                    {"SubnetId": "subnet-11111111"},
                    {"SubnetId": "subnet-22222222"}
                ],
                "SecurityGroups": ["sg-12345678"],
                "DNSName": "test-lb.ap-northeast-1.elb.amazonaws.com"
            }
        ]
    }]
    elbv2_client.get_paginator.return_value = paginator

    # describe_load_balancer_attributesのモックレスポンスを設定
    elbv2_client.describe_load_balancer_attributes.return_value = {
        "Attributes": [
            {
                "Key": "idle_timeout.timeout_seconds",
                "Value": "60"
            }
        ]
    }

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [
                {
                    "ResourceArn": kwargs["ResourceArns"][0],
                    "Tags": []
                }
            ]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect
    return collector
