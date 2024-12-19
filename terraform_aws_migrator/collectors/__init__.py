# terraform_aws_migrator/collectors/__init__.py

from .base import ResourceCollector, register_collector
from .aws_compute import *
from .aws_database import *
from .aws_network import *
from .aws_security import *
from .aws_storage import *
from .aws_application import *
from .aws_iam.role import IAMRoleCollector
from .aws_iam.user import IAMUserCollector
from .aws_iam.group import IAMGroupCollector
from .aws_iam.policy import IAMPolicyCollector

__all__ = [
    'ResourceCollector',
    'register_collector'
]
