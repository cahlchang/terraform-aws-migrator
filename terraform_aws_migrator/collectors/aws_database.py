# resource_collectors/database.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector


@register_collector
class RDSCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "rds"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_db_instance": "RDS Database Instances",
            "aws_rds_cluster": "RDS Database Clusters"
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # DB instances
            paginator = self.client.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for instance in page["DBInstances"]:
                    resources.append(
                        {
                            "type": "instance",
                            "id": instance["DBInstanceIdentifier"],
                            "arn": instance["DBInstanceArn"],
                            "engine": instance["Engine"],
                            "tags": self.client.list_tags_for_resource(
                                ResourceName=instance["DBInstanceArn"]
                            )["TagList"],
                        }
                    )

            # DB clusters
            paginator = self.client.get_paginator("describe_db_clusters")
            for page in paginator.paginate():
                for cluster in page["DBClusters"]:
                    resources.append(
                        {
                            "type": "cluster",
                            "id": cluster["DBClusterIdentifier"],
                            "arn": cluster["DBClusterArn"],
                            "engine": cluster["Engine"],
                            "tags": self.client.list_tags_for_resource(
                                ResourceName=cluster["DBClusterArn"]
                            )["TagList"],
                        }
                    )
        except Exception as e:
            print(f"Error collecting RDS resources: {str(e)}")

        return resources


@register_collector
class DynamoDBCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "dynamodb"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_dynamodb_table": "DynamoDB Tables"
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            paginator = self.client.get_paginator("list_tables")
            for page in paginator.paginate():
                for table_name in page["TableNames"]:
                    table = self.client.describe_table(TableName=table_name)["Table"]
                    tags = self.client.list_tags_of_resource(
                        ResourceArn=f"arn:aws:dynamodb:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:table/{table_name}"
                    ).get("Tags", [])

                    resources.append(
                        {
                            "type": "table",
                            "id": table_name,
                            "arn": table["TableArn"],
                            "tags": tags,
                        }
                    )
        except Exception as e:
            print(f"Error collecting DynamoDB tables: {str(e)}")

        return resources


@register_collector
class ElastiCacheCollector(ResourceCollector):
    @classmethod
    def get_service_name(self) -> str:
        return "elasticache"

    @classmethod
    def get_resource_types(self) -> Dict[str, str]:
        return {
            "aws_elasticache_cluster": "ElastiCache Clusters",
            "aws_elasticache_replication_group": "ElastiCache Replication Groups"
        }

    def collect(self) -> List[Dict[str, Any]]:
        resources = []

        try:
            # Cache clusters
            paginator = self.client.get_paginator("describe_cache_clusters")
            for page in paginator.paginate():
                for cluster in page["CacheClusters"]:
                    resources.append(
                        {
                            "type": "cluster",
                            "id": cluster["CacheClusterId"],
                            "arn": f"arn:aws:elasticache:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:cluster:{cluster['CacheClusterId']}",
                            "engine": cluster["Engine"],
                            "tags": self.client.list_tags_for_resource(
                                ResourceName=f"arn:aws:elasticache:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:cluster:{cluster['CacheClusterId']}"
                            )["TagList"],
                        }
                    )

            # Replication groups
            paginator = self.client.get_paginator("describe_replication_groups")
            for page in paginator.paginate():
                for group in page["ReplicationGroups"]:
                    resources.append(
                        {
                            "type": "replication_group",
                            "id": group["ReplicationGroupId"],
                            "arn": f"arn:aws:elasticache:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:replicationgroup:{group['ReplicationGroupId']}",
                            "tags": self.client.list_tags_for_resource(
                                ResourceName=f"arn:aws:elasticache:{self.session.region_name}:{self.session.client('sts').get_caller_identity()['Account']}:replicationgroup:{group['ReplicationGroupId']}"
                            )["TagList"],
                        }
                    )
        except Exception as e:
            print(f"Error collecting ElastiCache resources: {str(e)}")

        return resources

