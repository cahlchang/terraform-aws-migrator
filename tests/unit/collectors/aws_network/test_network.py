import pytest
from unittest.mock import MagicMock

from terraform_aws_migrator.collectors.aws_network.network import (
    LoadBalancerV2Collector,
    APIGatewayCollector,
    APIGatewayV2Collector,
    Route53Collector,
    CloudFrontCollector,
)

def test_generate_resource_identifier_with_arn(mock_session):
    """ARNを持つロードバランサーの識別子生成テスト"""
    collector = LoadBalancerV2Collector(mock_session)

    # Test load balancer with ARN
    lb_resource = {
        "type": "aws_lb",
        "id": "test-lb",
        "arn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890"
    }
    assert collector.generate_resource_identifier(lb_resource) == lb_resource["arn"]

def test_generate_resource_identifier_without_arn(mock_session):
    """ARNを持たないロードバランサーの識別子生成テスト"""
    collector = LoadBalancerV2Collector(mock_session)

    # Test load balancer without ARN
    lb_resource = {
        "type": "aws_lb",
        "id": "test-lb",
        "details": {
            "uuid": "1234567890"
        }
    }
    expected_lb_arn = f"arn:aws:elasticloadbalancing:{mock_session.region_name}:{collector.account_id}:loadbalancer/app/{lb_resource['id']}/1234567890"
    assert collector.generate_resource_identifier(lb_resource) == expected_lb_arn

def test_collect_load_balancers(mock_session):
    """ロードバランサー収集のテスト"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()

    # describe_load_balancersのモックレスポンスを設定
    lb_paginator = MagicMock()
    lb_paginator.paginate.return_value = [{
        "LoadBalancers": [{
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890",
            "LoadBalancerName": "test-lb",
            "Type": "application",
            "Scheme": "internal",
            "VpcId": "vpc-12345678",
            "State": {"Code": "active"},
            "SecurityGroups": ["sg-12345678"],
            "AvailabilityZones": [
                {"SubnetId": "subnet-11111111"},
                {"SubnetId": "subnet-22222222"}
            ],
            "DNSName": "test-lb.ap-northeast-1.elb.amazonaws.com"
        }]
    }]

    # describe_target_groupsのモックレスポンスを設定
    tg_paginator = MagicMock()
    tg_paginator.paginate.return_value = [{
        "TargetGroups": []
    }]

    # describe_listenersのモックレスポンスを設定
    listener_paginator = MagicMock()
    listener_paginator.paginate.return_value = [{
        "Listeners": []
    }]

    def get_paginator_side_effect(method):
        if method == 'describe_load_balancers':
            return lb_paginator
        elif method == 'describe_target_groups':
            return tg_paginator
        elif method == 'describe_listeners':
            return listener_paginator
        return MagicMock()

    elbv2_client.get_paginator.side_effect = get_paginator_side_effect

    # describe_load_balancer_attributesのモックレスポンスを設定
    elbv2_client.describe_load_balancer_attributes.return_value = {
        "Attributes": [{
            "Key": "idle_timeout.timeout_seconds",
            "Value": "60"
        }]
    }

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [{
                "ResourceArn": kwargs["ResourceArns"][0],
                "Tags": []
            }]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect

    # クライアントの設定を更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client.side_effect = get_client

    # state_readerのモックを設定
    mock_state_reader = MagicMock()
    mock_state_reader.get_managed_resources.return_value = {}
    collector.state_reader = mock_state_reader

    resources = collector.collect()
    lb_resources = [r for r in resources if r["type"] == "aws_lb"]

    assert len(lb_resources) == 1
    assert lb_resources[0]["id"] == "test-lb"
    assert lb_resources[0]["details"]["vpc_id"] == "vpc-12345678"
    assert lb_resources[0]["details"]["security_groups"] == ["sg-12345678"]
    assert lb_resources[0]["details"]["subnets"] == ["subnet-11111111", "subnet-22222222"]

def test_collect_target_groups(mock_session):
    """ターゲットグループ収集のテスト"""
    collector = LoadBalancerV2Collector(mock_session)

    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()

    # describe_target_groupsのモックレスポンスを設定
    tg_paginator = MagicMock()
    tg_paginator.paginate.return_value = [{
        "TargetGroups": [{
            "TargetGroupArn": "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/test-tg/0123456789",
            "TargetGroupName": "test-tg",
            "Protocol": "HTTP",
            "Port": 80,
            "VpcId": "vpc-12345678",
            "HealthCheckEnabled": True,
            "HealthCheckPath": "/health",
            "HealthCheckProtocol": "HTTP",
            "HealthCheckPort": "80",
            "HealthCheckIntervalSeconds": 30,
            "HealthCheckTimeoutSeconds": 5,
            "HealthyThresholdCount": 2,
            "UnhealthyThresholdCount": 2,
            "Matcher": {"HttpCode": "200"},
            "TargetType": "instance"
        }]
    }]

    def get_paginator_side_effect(method):
        if method == 'describe_target_groups':
            return tg_paginator
        return MagicMock()

    elbv2_client.get_paginator.side_effect = get_paginator_side_effect

    # describe_tagsのモックレスポンスを設定
    def describe_tags_side_effect(**kwargs):
        return {
            "TagDescriptions": [{
                "ResourceArn": kwargs["ResourceArns"][0],
                "Tags": []
            }]
        }
    elbv2_client.describe_tags.side_effect = describe_tags_side_effect

    # describe_target_group_attributesのモックレスポンスを設定
    elbv2_client.describe_target_group_attributes.return_value = {
        "Attributes": [
            {"Key": "deregistration_delay.timeout_seconds", "Value": "300"},
            {"Key": "lambda.multi_value_headers.enabled", "Value": "false"},
            {"Key": "proxy_protocol_v2.enabled", "Value": "false"},
            {"Key": "slow_start.duration_seconds", "Value": "0"}
        ]
    }

    # クライアントの設定を更新
    def get_client(service_name, *args, **kwargs):
        if service_name == 'elbv2':
            return elbv2_client
        elif service_name == 'sts':
            sts_client = MagicMock()
            sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
            return sts_client
        return MagicMock()

    mock_session.client.side_effect = get_client

    resources = collector.collect("aws_lb_target_group")
    tg_resources = [r for r in resources if r["type"] == "aws_lb_target_group"]

    assert len(tg_resources) == 1
    assert tg_resources[0]["id"] == "test-tg"
    assert tg_resources[0]["protocol"] == "HTTP"
    assert tg_resources[0]["port"] == 80
    assert tg_resources[0]["vpc_id"] == "vpc-12345678"
    assert tg_resources[0]["target_type"] == "instance"
    assert tg_resources[0]["health_check"]["path"] == "/health"

def test_api_gateway_collector(mocker):
    collector = APIGatewayCollector(mocker.Mock(), mocker.Mock())
    collector.client.get_rest_apis.return_value = {
        "items": [{
            "id": "api123",
            "name": "test-api",
            "tags": {"Environment": "test"}
        }]
    }

    resources = collector.collect()
    assert len(resources) == 1
    api = resources[0]
    assert api["type"] == "aws_api_gateway_rest_api"
    assert api["id"] == "api123"
    assert api["name"] == "test-api"
    assert api["tags"] == {"Environment": "test"}
    assert api["arn"] == f"arn:aws:apigateway:{collector.session.region_name}::/restapis/api123"

def test_api_gateway_collector_error(mocker):
    collector = APIGatewayCollector(mocker.Mock(), mocker.Mock())
    collector.client.get_rest_apis.side_effect = Exception("API Gateway error")
    
    resources = collector.collect()
    assert len(resources) == 0

def test_api_gateway_v2_collector(mocker):
    collector = APIGatewayV2Collector(mocker.Mock(), mocker.Mock())
    collector.client.get_apis.return_value = {
        "Items": [{
            "ApiId": "api456",
            "Name": "test-api-v2",
            "Tags": {"Environment": "test"}
        }]
    }

    resources = collector.collect()
    assert len(resources) == 1
    api = resources[0]
    assert api["type"] == "aws_apigatewayv2_api"
    assert api["id"] == "api456"
    assert api["name"] == "test-api-v2"
    assert api["tags"] == {"Environment": "test"}
    assert api["arn"] == f"arn:aws:apigateway:{collector.session.region_name}::/apis/api456"

def test_api_gateway_v2_collector_error(mocker):
    collector = APIGatewayV2Collector(mocker.Mock(), mocker.Mock())
    collector.client.get_apis.side_effect = Exception("API Gateway V2 error")
    
    resources = collector.collect()
    assert len(resources) == 0

def test_route53_collector(mocker):
    collector = Route53Collector(mocker.Mock(), mocker.Mock())
    
    # Mock paginator
    paginator_mock = mocker.Mock()
    paginator_mock.paginate.return_value = [{
        "HostedZones": [{
            "Id": "/hostedzone/Z123456789",
            "Name": "example.com."
        }]
    }]
    collector.client.get_paginator.return_value = paginator_mock
    
    # Mock tags
    collector.client.list_tags_for_resource.return_value = {
        "ResourceTagSet": {
            "Tags": [{"Key": "Environment", "Value": "test"}]
        }
    }

    resources = collector.collect()
    assert len(resources) == 1
    zone = resources[0]
    assert zone["type"] == "aws_route53_zone"
    assert zone["id"] == "/hostedzone/Z123456789"
    assert zone["name"] == "example.com."
    assert zone["tags"] == [{"Key": "Environment", "Value": "test"}]

def test_route53_collector_error(mocker):
    collector = Route53Collector(mocker.Mock(), mocker.Mock())
    collector.client.get_paginator.side_effect = Exception("Route53 error")
    
    resources = collector.collect()
    assert len(resources) == 0

def test_cloudfront_collector(mocker):
    collector = CloudFrontCollector(mocker.Mock(), mocker.Mock())
    
    # Mock paginator
    paginator_mock = mocker.Mock()
    paginator_mock.paginate.return_value = [{
        "DistributionList": {
            "Items": [{
                "Id": "E123456789",
                "ARN": "arn:aws:cloudfront::123456789012:distribution/E123456789",
                "DomainName": "d123.cloudfront.net"
            }]
        }
    }]
    collector.client.get_paginator.return_value = paginator_mock
    
    # Mock tags
    collector.client.list_tags_for_resource.return_value = {
        "Tags": {
            "Items": [{"Key": "Environment", "Value": "test"}]
        }
    }

    resources = collector.collect()
    assert len(resources) == 1
    dist = resources[0]
    assert dist["type"] == "aws_cloudfront_distribution"
    assert dist["id"] == "E123456789"
    assert dist["domain_name"] == "d123.cloudfront.net"
    assert dist["arn"] == "arn:aws:cloudfront::123456789012:distribution/E123456789"
    assert dist["tags"] == [{"Key": "Environment", "Value": "test"}]

def test_cloudfront_collector_error(mocker):
    collector = CloudFrontCollector(mocker.Mock(), mocker.Mock())
    collector.client.get_paginator.side_effect = Exception("CloudFront error")
    
    resources = collector.collect()
    assert len(resources) == 0

def test_generate_resource_identifier_fallback(mock_session):
    collector = LoadBalancerV2Collector(mock_session)

    # Test fallback case with only type and id
    resource = {
        "type": "unknown_type",
        "id": "test-id"
    }
    assert collector.generate_resource_identifier(resource) == "unknown_type:test-id"

    # Test fallback case with only id
    resource = {
        "id": "test-id"
    }
    assert collector.generate_resource_identifier(resource) == "test-id"

    # Test fallback case with empty resource
    resource = {}
    assert collector.generate_resource_identifier(resource) == ""
