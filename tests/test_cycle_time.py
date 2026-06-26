from datetime import datetime, timedelta
import pytest
from src.models import PRStatus
from src.analytics.cycle_time import calculate_cycle_time, calculate_stall_duration

def test_calculate_cycle_time_merged(make_pr):
    """calculate_cycle_time should return the correct hour difference for a merged/closed PR."""
    created = datetime.utcnow() - timedelta(hours=48)
    merged = datetime.utcnow() - timedelta(hours=24)
    
    pr = make_pr(created_at=created, merged_at=merged, status=PRStatus.MERGED)
    cycle_time = calculate_cycle_time(pr)
    
    assert cycle_time is not None
    # 48 - 24 = 24 hours difference
    assert pytest.approx(cycle_time, 0.01) == 24.0

def test_calculate_cycle_time_open(make_pr):
    """calculate_cycle_time should return None for an open PR."""
    pr = make_pr(status=PRStatus.OPEN, merged_at=None, closed_at=None)
    cycle_time = calculate_cycle_time(pr)
    assert cycle_time is None

def test_calculate_stall_duration(make_pr):
    """calculate_stall_duration should return the correct hour difference since last_activity_at."""
    last_act = datetime.utcnow() - timedelta(hours=36)
    pr = make_pr(last_activity_at=last_act)
    
    stall_dur = calculate_stall_duration(pr)
    # The elapsed time since last_activity_at should be approximately 36 hours
    assert pytest.approx(stall_dur, 0.01) == 36.0
