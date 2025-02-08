import pytest
from unittest.mock import MagicMock

from terraform_aws_migrator.collectors.aws_network.network import LoadBalancerV2Collector

def test_generate_resource_identifier_with_arn(mock_session, sample_state_data, mock_collector):
    collector = mock_collector

    # Test load balancer with ARN
    lb_resource = {
        "type": "aws_lb",
        "id": "test-lb"
    }
    expected_lb_arn = f"arn:aws:elasticloadbalancing:{mock_session.region_name}:{collector.account_id}:loadbalancer/app/{lb_resource['id']}/1234567890"
    assert collector.generate_resource_identifier(lb_resource) == expected_lb_arn

def test_generate_resource_identifier_without_arn(mock_session, sample_state_data, mock_collector):
    collector = mock_collector

    # Test load balancer without ARN
    lb_resource = {
        "type": "aws_lb",  # カンマを追加
        "id": "test-lb"
    }
    expected_lb_arn = f"arn:aws:elasticloadbalancing:{mock_session.region_name}:{collector.account_id}:loadbalancer/app/{lb_resource['id']}/1234567890"
    assert collector.generate_resource_identifier(lb_resource) == expected_lb_arn

def test_collect_resources(mock_session, sample_state_data, mock_collector):
    collector = mock_collector
    
    # テスト用のモックリソースを設定
    collector._mock_resources = [{
        "type": "aws_lb",
        "id": "test-lb",
        "arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890",
        "tags": [],
        "details": {
            "dns_name": "test-lb.ap-northeast-1.elb.amazonaws.com",
            "scheme": "internet-facing",
            "vpc_id": "vpc-12345678",
            "security_groups": ["sg-12345678"],
            "subnets": ["subnet-11111111", "subnet-22222222"],
            "state": "active",
            "uuid": "1234567890"
        }
    }]
    
    resources = collector.collect()

    # Verify load balancer collection
    lb_resources = [r for r in resources if r["type"] == "aws_lb"]
    assert len(lb_resources) == 1
    
    # リソースの詳細を検証
    lb = lb_resources[0]
    assert lb["id"] == "test-lb"
    assert lb["arn"] == "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890"
    assert lb["details"]["vpc_id"] == "vpc-12345678"

# 他のテストケースも同様に修正してください
