import pytest
from unittest.mock import patch
from rich.text import Text
from terraform_aws_migrator.progress_tracking import CompactTimeColumn, TimeTracker

@pytest.fixture
def time_column():
    return CompactTimeColumn()

@pytest.fixture
def time_tracker():
    return TimeTracker()

def test_compact_time_column_render(time_column):
    with patch('time.time') as mock_time:
        # Set initial time
        mock_time.return_value = 1000
        time_column.start_time = 1000

        # Test 1 minute elapsed
        mock_time.return_value = 1060
        result = time_column.render(None)
        assert isinstance(result, Text)
        assert result.plain == "[01:00]"

        # Test multiple minutes elapsed
        mock_time.return_value = 1180
        result = time_column.render(None)
        assert result.plain == "[03:00]"

def test_time_tracker_start(time_tracker):
    with patch('time.time') as mock_time:
        mock_time.return_value = 1000
        time_tracker.start()
        assert time_tracker.start_time == 1000

def test_time_tracker_get_elapsed_time_not_started(time_tracker):
    result = time_tracker.get_elapsed_time()
    assert result == "[00:00]"

def test_time_tracker_get_elapsed_time(time_tracker):
    with patch('time.time') as mock_time:
        # Set start time
        mock_time.return_value = 1000
        time_tracker.start()

        # Test 1 minute elapsed
        mock_time.return_value = 1060
        result = time_tracker.get_elapsed_time()
        assert result == "[01:00]"

        # Test multiple minutes elapsed
        mock_time.return_value = 1180
        result = time_tracker.get_elapsed_time()
        assert result == "[03:00]"

def test_time_tracker_get_total_time_not_started(time_tracker):
    result = time_tracker.get_total_time()
    assert result is None

def test_time_tracker_get_total_time(time_tracker):
    with patch('time.time') as mock_time:
        # Set start time
        mock_time.return_value = 1000
        time_tracker.start()

        # Test 1 minute elapsed
        mock_time.return_value = 1060
        result = time_tracker.get_total_time()
        assert result == "[01:00]"

        # Test multiple minutes elapsed
        mock_time.return_value = 1180
        result = time_tracker.get_total_time()
        assert result == "[03:00]"

def test_time_tracker_multiple_starts(time_tracker):
    with patch('time.time') as mock_time:
        # First start
        mock_time.return_value = 1000
        time_tracker.start()

        # Second start should override first
        mock_time.return_value = 2000
        time_tracker.start()

        # Elapsed time should be calculated from second start
        mock_time.return_value = 2060
        result = time_tracker.get_elapsed_time()
        assert result == "[01:00]"
