from .role import IAMRoleCollector
from .user import IAMUserCollector
from .group import IAMGroupCollector
from .policy import IAMPolicyCollector

__all__ = [
    'IAMRoleCollector',
    'IAMUserCollector',
    'IAMGroupCollector',
    'IAMPolicyCollector'
]
