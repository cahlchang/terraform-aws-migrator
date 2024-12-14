# resource_collectors/storage.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector

@register_collector
class S3Collector(ResourceCollector):
    def get_service_name(self) -> str:
        return 's3'
    
    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        
        try:
            for bucket in self.client.list_buckets()['Buckets']:
                bucket_name = bucket['Name']
                try:
                    tags = self.client.get_bucket_tagging(Bucket=bucket_name).get('TagSet', [])
                except:
                    tags = []
                
                resources.append({
                    'type': 'bucket',
                    'id': bucket_name,
                    'arn': f"arn:aws:s3:::{bucket_name}",
                    'tags': tags
                })
        except Exception as e:
            print(f"Error collecting S3 buckets: {str(e)}")
            
        return resources

@register_collector
class EFSCollector(ResourceCollector):
    def get_service_name(self) -> str:
        return 'efs'
    
    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        
        try:
            paginator = self.client.get_paginator('describe_file_systems')
            for page in paginator.paginate():
                for fs in page['FileSystems']:
                    resources.append({
                        'type': 'filesystem',
                        'id': fs['FileSystemId'],
                        'arn': fs['FileSystemArn'],
                        'tags': fs.get('Tags', [])
                    })
        except Exception as e:
            print(f"Error collecting EFS filesystems: {str(e)}")
            
        return resources

@register_collector
class EBSCollector(ResourceCollector):
    def get_service_name(self) -> str:
        return 'ec2'  # API call is made to EC2 service
    
    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        
        try:
            paginator = self.client.get_paginator('describe_volumes')
            for page in paginator.paginate():
                for volume in page['Volumes']:
                    resources.append({
                        'type': 'volume',
                        'id': volume['VolumeId'],
                        'arn': f"arn:aws:ec2:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:volume/{volume['VolumeId']}",
                        'size': volume['Size'],
                        'tags': volume.get('Tags', [])
                    })
        except Exception as e:
            print(f"Error collecting EBS volumes: {str(e)}")
            
        return resources
