import pytest
import logging
from unittest.mock import MagicMock
from terraform_aws_migrator.collectors.aws_network.network import LoadBalancerV2Collector

logger = logging.getLogger(__name__)

def test_collect_load_balancers_managed(mock_session):
    """Normal case: Test of managed load balancer"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()

    # paginatorのモックを設定
    paginator_mock = MagicMock()
    paginator_mock.paginate.return_value = [{
        "LoadBalancers": [{
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890",
            "LoadBalancerName": "test-lb",
            "Type": "application",
            "Scheme": "internal",
            "VpcId": "vpc-87654321",
            "State": {"Code": "active"},
            "SecurityGroups": ["sg-87654321"],
            "AvailabilityZones": [
                {"SubnetId": "subnet-33333333"},
                {"SubnetId": "subnet-44444444"}
            ],
            "DNSName": "test-lb.ap-northeast-1.elb.amazonaws.com"
        }]
    }]

    def get_paginator(method):
        if method == "describe_load_balancers":
            return paginator_mock
        return MagicMock()

    elbv2_client.get_paginator = MagicMock(side_effect=get_paginator)

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [{
                "ResourceArn": kwargs["ResourceArns"][0],
                "Tags": []
            }]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect

    # セッションのクライアントメソッドを更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client = MagicMock(side_effect=get_client)

    # state_readerのモックを設定
    mock_state_reader = MagicMock()
    managed_resources = {
        "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890": {
            "type": "aws_lb",
            "id": "test-lb",
            "managed": True
        }
    }
    mock_state_reader.get_managed_resources.return_value = managed_resources
    collector.state_reader = mock_state_reader

    resources = collector.collect()
    lb_resources = [r for r in resources if r["type"] == "aws_lb"]

    # 実際に存在するLBの確認
    assert len(lb_resources) == 1
    assert lb_resources[0]["id"] == "test-lb"
    assert lb_resources[0]["managed"] is True
    assert lb_resources[0]["details"]["vpc_id"] == "vpc-87654321"
    assert lb_resources[0]["details"]["security_groups"] == ["sg-87654321"]
    assert lb_resources[0]["details"]["subnets"] == ["subnet-33333333", "subnet-44444444"]

def test_collect_load_balancers_with_tags(mock_session):
    """Normal case: Test of tagged load balancer"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()

    # paginatorのモックを設定
    paginator_mock = MagicMock()
    paginator_mock.paginate.return_value = [{
        "LoadBalancers": [{
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/tagged-lb/4444444444",
            "LoadBalancerName": "tagged-lb",
            "Type": "application",
            "Scheme": "internal",
            "VpcId": "vpc-44444444",
            "State": {"Code": "active"},
            "SecurityGroups": ["sg-44444444"],
            "AvailabilityZones": [
                {"SubnetId": "subnet-55555555"},
                {"SubnetId": "subnet-66666666"}
            ],
            "DNSName": "tagged-lb.ap-northeast-1.elb.amazonaws.com"
        }]
    }]

    def get_paginator(method):
        if method == "describe_load_balancers":
            return paginator_mock
        return MagicMock()

    elbv2_client.get_paginator = MagicMock(side_effect=get_paginator)

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [{
                "ResourceArn": kwargs["ResourceArns"][0],
                "Tags": [
                    {"Key": "Environment", "Value": "Production"},
                    {"Key": "Name", "Value": "Tagged-LB"},
                    {"Key": "Project", "Value": "Test"}
                ]
            }]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect

    # セッションのクライアントメソッドを更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client = MagicMock(side_effect=get_client)

    # state_readerのモックを設定
    mock_state_reader = MagicMock()
    mock_state_reader.get_managed_resources.return_value = {}
    collector.state_reader = mock_state_reader

    resources = collector.collect()
    lb_resources = [r for r in resources if r["type"] == "aws_lb"]

    assert len(lb_resources) == 1
    assert lb_resources[0]["id"] == "tagged-lb"
    assert len(lb_resources[0]["tags"]) == 3
    assert any(tag["Key"] == "Environment" and tag["Value"] == "Production" for tag in lb_resources[0]["tags"])
    assert any(tag["Key"] == "Name" and tag["Value"] == "Tagged-LB" for tag in lb_resources[0]["tags"])
    assert any(tag["Key"] == "Project" and tag["Value"] == "Test" for tag in lb_resources[0]["tags"])

def test_collect_load_balancers_unmanaged(mock_session):
    """Normal case: Test of unmanaged load balancer"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()

    # paginatorのモックを設定
    paginator_mock = MagicMock()
    paginator_mock.paginate.return_value = [{
        "LoadBalancers": [{
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/unmanaged-lb/9876543210",
            "LoadBalancerName": "unmanaged-lb",
            "Type": "application",
            "Scheme": "internal",
            "VpcId": "vpc-87654321",
            "State": {"Code": "active"},
            "SecurityGroups": ["sg-87654321"],
            "AvailabilityZones": [
                {"SubnetId": "subnet-33333333"},
                {"SubnetId": "subnet-44444444"}
            ],
            "DNSName": "unmanaged-lb.ap-northeast-1.elb.amazonaws.com"
        }]
    }]

    def get_paginator(method):
        if method == "describe_load_balancers":
            return paginator_mock
        return MagicMock()

    elbv2_client.get_paginator = MagicMock(side_effect=get_paginator)

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [{
                "ResourceArn": kwargs["ResourceArns"][0],
                "Tags": []
            }]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect

    # セッションのクライアントメソッドを更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client = MagicMock(side_effect=get_client)

    # state_readerのモックを設定
    mock_state_reader = MagicMock()
    mock_state_reader.get_managed_resources.return_value = {}
    collector.state_reader = mock_state_reader

    resources = collector.collect()
    lb_resources = [r for r in resources if r["type"] == "aws_lb"]
    assert len(lb_resources) == 1
    assert lb_resources[0]["id"] == "unmanaged-lb"
    assert not lb_resources[0].get("managed", False)

def test_collect_module_load_balancers(mock_session):
    """Normal case: Test of load balancer within module"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()

    # paginatorのモックを設定
    paginator_mock = MagicMock()
    paginator_mock.paginate.return_value = [{
        "LoadBalancers": [{
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/module-lb/5555555555",
            "LoadBalancerName": "module-lb",
            "Type": "application",
            "Scheme": "internal",
            "VpcId": "vpc-55555555",
            "State": {"Code": "active"},
            "SecurityGroups": ["sg-55555555"],
            "AvailabilityZones": [
                {"SubnetId": "subnet-55555555"},
                {"SubnetId": "subnet-66666666"}
            ],
            "DNSName": "module-lb.ap-northeast-1.elb.amazonaws.com"
        }]
    }]

    def get_paginator(method):
        if method == "describe_load_balancers":
            return paginator_mock
        return MagicMock()

    elbv2_client.get_paginator = MagicMock(side_effect=get_paginator)

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [{
                "ResourceArn": kwargs["ResourceArns"][0],
                "Tags": []
            }]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect

    # セッションのクライアントメソッドを更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client = MagicMock(side_effect=get_client)

    # モジュール内の管理されたリソース
    managed_resources = {
        "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/module-lb/5555555555": {
            "type": "aws_lb",
            "id": "module-lb",
            "managed": True,
            "module": "test_module"
        }
    }
    mock_state_reader = MagicMock()
    mock_state_reader.get_managed_resources.return_value = managed_resources
    collector.state_reader = mock_state_reader

    resources = collector.collect()
    lb_resources = [r for r in resources if r["type"] == "aws_lb"]
    assert len(lb_resources) == 1
    assert lb_resources[0]["id"] == "module-lb"
    assert lb_resources[0].get("managed") is True
    assert lb_resources[0].get("module") == "test_module"

def test_generate_resource_identifier_with_arn(mock_collector):
    """Test resource identifier generation with ARN"""
    resource = {
        "type": "aws_lb",
        "id": "test-lb",
        "arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890"
    }
    identifier = mock_collector.generate_resource_identifier(resource)
    assert identifier == resource["arn"]

def test_generate_resource_identifier_without_arn(mock_collector):
    """Test resource identifier generation without ARN"""
    resource = {
        "type": "aws_lb",
        "id": "test-lb"
    }
    identifier = mock_collector.generate_resource_identifier(resource)
    expected = f"arn:aws:elasticloadbalancing:{mock_collector.session.region_name}:{mock_collector.account_id}:loadbalancer/app/{resource['id']}/1234567890"
    assert identifier == expected

def test_error_handling(mock_session):
    """Test error handling during resource collection"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定してエラーを発生させる
    elbv2_client = MagicMock()
    paginator_mock = MagicMock()
    paginator_mock.paginate.side_effect = Exception("Test error")

    def get_paginator(method):
        if method == "describe_load_balancers":
            return paginator_mock
        return MagicMock()

    elbv2_client.get_paginator = MagicMock(side_effect=get_paginator)

    # セッションのクライアントメソッドを更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client = MagicMock(side_effect=get_client)

    # エラーが発生しても空のリストが返されることを確認
    resources = collector.collect()
    assert len(resources) == 0
