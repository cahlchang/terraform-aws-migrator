# terraform_aws_migrator/collection_status.py

from typing import Optional
from datetime import datetime
from rich.table import Table
from rich.text import Text
from rich import box


class CollectionStatus:
    def __init__(self):
        self.services_status = {}
        self.current_task = ""
        self.current_file = ""
        self.elapsed_time = 0.0

    def update_task(self, task: str, file: str = "", time: float = 0.0):
        self.current_task = task
        self.current_file = file
        self.elapsed_time = time

    def update_service(
        self, service_name: str, status: str, resource_count: Optional[int] = None
    ):
        self.services_status[service_name] = {
            "status": status,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "resource_count": resource_count,
        }

    def get_progress_text(self) -> Text:
        text = Text()
        if self.current_task:
            mins, secs = divmod(int(self.elapsed_time), 60)
            if mins > 0:
                time_str = f"{mins}m {secs}s"
            else:
                time_str = f"{secs}s"

            text.append(f"[→] ", style="bold yellow")
            text.append(f"{self.current_task} ", style="bold white")
            text.append(f"({time_str})", style="cyan")
        return text

    def get_table(self) -> Table:
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
            title=None,
            collapse_padding=True,
            pad_edge=False,
            width=60,
        )

        # compact column style
        table.add_column("Service", style="bold", width=15)
        table.add_column("Status", style="cyan", width=12)
        table.add_column("Resources", justify="right", width=10)

        # add dataset
        for service, info in self.services_status.items():
            status_style = "green" if info["status"] == "Completed" else "yellow"
            resource_count = (
                str(info["resource_count"])
                if info["resource_count"] is not None
                else "-"
            )

            table.add_row(
                service,
                f"[{status_style}]{info['status']}[/{status_style}]",
                resource_count,
            )

        return table
