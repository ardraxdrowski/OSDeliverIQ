from datetime import datetime
from typing import Optional
from src.models import PullRequest, PRStatus

def calculate_cycle_time(pr: PullRequest) -> Optional[float]:
    """Calculates hours from created_at to merged_at/closed_at. Returns None if PR is still open."""
    if pr.status == PRStatus.OPEN or (not pr.merged_at and not pr.closed_at):
        return None
    
    end_time = pr.merged_at if pr.merged_at else pr.closed_at
    if not end_time or not pr.created_at:
        return None
        
    return (end_time - pr.created_at).total_seconds() / 3600

def calculate_review_lag(pr: PullRequest, first_review_submitted_at: Optional[datetime]) -> Optional[float]:
    """Calculates hours from created_at to first review."""
    if not pr.created_at or not first_review_submitted_at:
        return None
        
    return (first_review_submitted_at - pr.created_at).total_seconds() / 3600

def calculate_stall_duration(pr: PullRequest) -> float:
    """Calculates hours since last_activity_at to now."""
    if not pr.last_activity_at:
        return 0.0
    now = datetime.utcnow()
    return (now - pr.last_activity_at).total_seconds() / 3600
