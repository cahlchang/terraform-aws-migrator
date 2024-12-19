# terraform_aws_migrator/formatters/output_formatter.py

import json
import time
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
import logging

logger = logging.getLogger(__name__)


class ProgressFormatter:
    """Format progress output with rich text formatting and spinning animation"""

    def __init__(self):
        self.console = Console()
        self.spinner_idx = 0
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.last_spinner_update = time.time()
        self.spinner_interval = 0.1  # Update spinner every 100ms

    def _get_spinner(self) -> str:
        """Get current spinner frame and update counter"""
        current_time = time.time()
        if current_time - self.last_spinner_update >= self.spinner_interval:
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            self.last_spinner_update = current_time
        return self.spinner_chars[self.spinner_idx]

    def create_progress_table(self, resources: List[Dict[str, Any]]) -> Table:
        """Create a rich Table showing current progress"""
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            collapse_padding=True,
            show_edge=False,
        )

        # Sort resources to show processing items first
        sorted_resources = sorted(
            resources, key=lambda x: (x["status"] != "Processing", x["service"])
        )

        for resource in sorted_resources:
            status = resource["status"]
            service = resource["service"]
            duration = resource["time"]

            # Create text with appropriate styling
            row = Text()

            if status == "Processing":
                spinner = self._get_spinner()
                row.append(f"{spinner} ", style="yellow")
                row.append(f"{service:<20}", style="yellow")
                row.append(duration, style="yellow")
            elif status == "Completed":
                row.append("✓ ", style="green")
                row.append(f"{service:<20}", style="green")
                row.append(duration, style="green")
            elif status == "Failed":
                row.append("✗ ", style="red")
                row.append(f"{service:<20}", style="red")
                row.append(duration, style="red")

            table.add_row(row)

        return table


def format_progress(resources: List[Dict[str, Any]]) -> Table:
    """Format progress information into a rich Table"""
    formatter = ProgressFormatter()
    return formatter.create_progress_table(resources)


def format_output(
    resources: Dict[str, List[Dict[str, Any]]], output_format: str = "text"
) -> str:
    """Format the final output of unmanaged resources"""
    try:
        if output_format == "json":
            return json.dumps(resources, indent=2, default=str)

        if not resources:
            return "No unmanaged resources found."

        # Format text output
        output = []
        output.append("\nUnmanaged AWS Resources:")
        output.append("=" * 40)

        for service_name, service_resources in sorted(resources.items()):
            if not service_resources:
                continue

            output.append(f"\n[{service_name}]")
            for resource in service_resources:
                output.append(f"\nType: {resource.get('type', 'unknown')}")
                output.append(f"ID: {resource.get('id', 'N/A')}")
                output.append(f"ARN: {resource.get('arn', 'N/A')}")

                # Add details if present
                if details := resource.get("details"):
                    output.append("Details:")
                    for key, value in sorted(details.items()):
                        output.append(f"  {key}: {value}")

                # Add tags if present
                if tags := resource.get("tags"):
                    output.append("Tags:")
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, dict):
                                output.append(
                                    f"  {tag.get('Key', 'N/A')}: {tag.get('Value', 'N/A')}"
                                )
                    elif isinstance(tags, dict):
                        for key, value in sorted(tags.items()):
                            output.append(f"  {key}: {value}")

        return "\n".join(output)

    except Exception as e:
        logger.exception("Error formatting output")
        return f"Error formatting output: {str(e)}"
