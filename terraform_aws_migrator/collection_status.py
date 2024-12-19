# terraform_aws_migrator/collection_status.py

from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CollectionStatus:
    """Track the status of resource collection"""

    service: str
    status: str
    start_time: datetime
    end_time: datetime = None

    @property
    def duration(self) -> str:
        """Format duration as [MM:SS]"""
        if not self.end_time:
            duration = datetime.now() - self.start_time
        else:
            duration = self.end_time - self.start_time

        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"[{minutes:02d}:{seconds:02d}]"


class StatusTracker:
    """Track collection status across multiple services"""

    def __init__(self):
        self.statuses: Dict[str, CollectionStatus] = {}

    def start_collection(self, service: str):
        """Record the start of collection for a service"""
        self.statuses[service] = CollectionStatus(
            service=service, status="Processing", start_time=datetime.now()
        )

    def complete_collection(self, service: str, success: bool = True):
        """Record the completion of collection for a service"""
        if service in self.statuses:
            status = self.statuses[service]
            status.status = "Completed" if success else "Failed"
            status.end_time = datetime.now()

    def get_progress_data(self) -> List[Dict[str, Any]]:
        """Get formatted progress data for all services"""
        progress_data = []
        for status in self.statuses.values():
            progress_data.append(
                {
                    "service": status.service,
                    "status": status.status,
                    "time": status.duration,
                }
            )
        return sorted(
            progress_data, key=lambda x: (x["status"] != "Processing", x["service"])
        )


# Ensure the class is properly exported
__all__ = ["StatusTracker", "CollectionStatus"]
