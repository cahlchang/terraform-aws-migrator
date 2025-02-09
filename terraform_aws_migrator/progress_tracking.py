import time
from typing import Optional
from rich.progress import ProgressColumn, Task
from rich.text import Text

class CompactTimeColumn(ProgressColumn):
    """Custom time column that displays elapsed time in a compact format"""

    def __init__(self):
        super().__init__()
        self.start_time = time.time()

    def render(self, task: "Task") -> Text:
        """Render the time column."""
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return Text(f"[{minutes:02d}:{seconds:02d}]")

class TimeTracker:
    """Class for tracking execution time"""

    def __init__(self):
        self.start_time: Optional[float] = None

    def start(self):
        """Start tracking time"""
        self.start_time = time.time()

    def get_elapsed_time(self) -> str:
        """Get elapsed time in MM:SS format"""
        if self.start_time is None:
            return "[00:00]"
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"[{minutes:02d}:{seconds:02d}]"

    def get_total_time(self) -> Optional[str]:
        """Get total execution time in MM:SS format"""
        if self.start_time is None:
            return None
        total_time = int(time.time() - self.start_time)
        minutes = total_time // 60
        seconds = total_time % 60
        return f"[{minutes:02d}:{seconds:02d}]"
