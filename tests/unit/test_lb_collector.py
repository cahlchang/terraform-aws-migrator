# tests/unit/test_lb_collector.py

import unittest
from unittest.mock import MagicMock, patch
from terraform_aws_migrator.collectors.aws_network.network import LoadBalancerV2Collector
from typing import Dict, Any

class TestLoadBalancerV2Collector(unittest.TestCase):
    def setUp(self):
        self.collector = LoadBalancerV2Collector()
        self.collector.session = MagicMock()
        self.collector.session.region_name = "dummy-region"
        self.collector._account_id = "000000000000"

    @patch.object(LoadBalancerV2Collector, 'client', new_callable=MagicMock)
    def test_collect_load_balancers_managed(self, mock_client):
        # モックされた client の動作を設定
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "LoadBalancers": [
                    {
                        "LoadBalancerName": "dummy-lb",
                        "LoadBalancerArn": "arn:aws:elasticloadbalancing:dummy-region:000000000000:loadbalancer/app/dummy-lb/dummy-id",
                        "Type": "application",
                        "Tags": [
                            {"Key": "dummy_key", "Value": "dummy_value"}
                        ],
                        "DNSName": "dummy-lb.dummy-region.elb.amazonaws.com",
                        "Scheme": "internal",
                        "VpcId": "dummy-vpc",
                        "IdleTimeout": {"TimeoutSeconds": 100},
                        "SecurityGroups": ["dummy-sg"],
                        "AvailabilityZones": [
                            {"SubnetId": "dummy-subnet-1"},
                            {"SubnetId": "dummy-subnet-2"}
                        ],
                        "State": {"Code": "active"},
                        "IpAddressType": "ipv4",
                        "LoadBalancerAttributes": [
                            {"Key": "dummy_attr", "Value": "dummy_value"}
                        ]
                    }
                ]
            }
        ]

        state_data = {
            "version": 4,
            "terraform_version": "dummy-version",
            "serial": 1,
            "lineage": "dummy-lineage",
            "outputs": {},
            "resources": [
                {
                    "module": "dummy-module",
                    "mode": "managed",
                    "type": "aws_lb",
                    "name": "dummy-lb-resource",
                    "provider": "dummy-provider",
                    "instances": [
                        {
                            "schema_version": 0,
                            "attributes": {
                                "arn": "arn:aws:elasticloadbalancing:dummy-region:000000000000:loadbalancer/app/dummy-lb/dummy-id",
                                "arn_suffix": "app/dummy-lb/dummy-id",
                                "client_keep_alive": 100,
                                "desync_mitigation_mode": "dummy-desync",
                                "dns_name": "dummy-lb.dummy-region.elb.amazonaws.com",
                                "drop_invalid_header_fields": False,
                                "enable_cross_zone_load_balancing": True,
                                "enable_deletion_protection": False,
                                "enable_http2": True,
                                "enable_tls_version_and_cipher_suite_headers": False,
                                "enable_waf_fail_open": False,
                                "enable_xff_client_port": False,
                                "enable_zonal_shift": False,
                                "id": "arn:aws:elasticloadbalancing:dummy-region:000000000000:loadbalancer/app/dummy-lb/dummy-id",
                                "idle_timeout": 100,
                                "internal": True,
                                "ip_address_type": "ipv4",
                                "load_balancer_type": "application",
                                "name": "dummy-lb-name",
                                "preserve_host_header": False,
                                "security_groups": [
                                    "dummy-sg"
                                ],
                                "subnets": [
                                    "dummy-subnet-1",
                                    "dummy-subnet-2"
                                ],
                                "tags": {},
                                "tags_all": {
                                    "dummy_tag": "dummy_value"
                                },
                                "vpc_id": "dummy-vpc",
                                "xff_header_processing_mode": "dummy-xff",
                                "zone_id": "dummy-zone"
                            }
                        }
                    ]
                }
            ]
        }

        managed_resources = {}
        self.collector._extract_resources_from_state(state_data, managed_resources)

        dummy_arn = "arn:aws:elasticloadbalancing:dummy-region:000000000000:loadbalancer/app/dummy-lb/dummy-id"
        # 管理リソースとして正しく抽出されていることを確認
        self.assertIn(dummy_arn, managed_resources)
        self.assertTrue(managed_resources[dummy_arn]["managed"])

if __name__ == '__main__':
    unittest.main()
