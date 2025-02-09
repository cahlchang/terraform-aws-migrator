import pytest
from unittest.mock import MagicMock, patch
from terraform_aws_migrator.collectors.aws_network.network import LoadBalancerV2Collector

class MockStreamingBody:
    """S3のストリーミングボディをモックするクラス"""
    def __init__(self, content):
        if isinstance(content, str):
            self._content = content.encode('utf-8')
        elif isinstance(content, bytes):
            self._content = content
        else:
            self._content = str(content).encode('utf-8')
        self._closed = False
        self._position = 0

    def read(self, size=None):
        """コンテンツを読み取る"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        # 位置が末尾を超えている場合は空のバイト列を返す
        if self._position >= len(self._content):
            return b''
        
        if size is None:
            # 全体を読み取る場合
            result = self._content[self._position:]
            self._position = len(self._content)
        else:
            # 指定されたサイズだけ読み取る
            result = self._content[self._position:self._position + size]
            self._position += len(result)
        
        return result

    def seek(self, offset, whence=0):
        """ストリームの位置を移動する"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if whence == 0:  # SEEK_SET
            self._position = offset
        elif whence == 1:  # SEEK_CUR
            self._position += offset
        elif whence == 2:  # SEEK_END
            self._position = len(self._content) + offset
        
        if self._position < 0:
            self._position = 0
        elif self._position > len(self._content):
            self._position = len(self._content)
        
        return self._position

    def close(self):
        """ストリームをクローズする"""
        self._closed = True

class MockClientError(Exception):
    """AWSのClientErrorをモックするクラス"""
    def __init__(self, error_code="400", message="Mocked AWS Error"):
        self.response = {"Error": {"Code": error_code, "Message": message}}
        super().__init__(message)

@pytest.fixture
def mock_session():
    # モックされたセッションオブジェクトを作成
    mock = MagicMock()
    mock.region_name = "ap-northeast-1"
    mock.account_id = "123456789012"  # アカウントIDを設定

    # STSクライアントのモックを作成
    sts_client = MagicMock()
    sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

    # S3クライアントのモックを作成
    s3_client = MagicMock()
    s3_client.exceptions = MagicMock()
    s3_client.exceptions.ClientError = MockClientError
    s3_client.get_object = MagicMock()
    s3_client.head_object = MagicMock()

    # クライアントのモックを設定
    def get_client(service_name, *args, **kwargs):
        if service_name == 'sts':
            return sts_client
        elif service_name == 's3':
            return s3_client
        return MagicMock()
    
    mock.client = MagicMock(side_effect=get_client)

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
            }
        ]
    }
    return sample_data

@pytest.fixture
def mock_collector(mock_session):
    """LoadBalancerV2Collectorのモックを提供するフィクスチャ"""
    collector = LoadBalancerV2Collector(mock_session)
    
    # ELBv2クライアントのモックを設定
    elbv2_client = MagicMock()
    
    # describe_load_balancersのモックレスポンスを設定
    elbv2_client.describe_load_balancers.return_value = {
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

    # state_readerのモックを作成と設定
    mock_state_reader = MagicMock()
    mock_state_reader.get_managed_resources.return_value = {
        "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:loadbalancer/app/test-lb/1234567890": {
            "type": "aws_lb",
            "id": "test-lb",
            "managed": True
        }
    }
    collector.state_reader = mock_state_reader

    return collector
