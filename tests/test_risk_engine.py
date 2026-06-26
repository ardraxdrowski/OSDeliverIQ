from datetime import datetime, timedelta
import pytest
from src.models import PRStatus, RiskTier
from src.analytics.risk_engine import assign_risk_tier, detect_stall_reason, run_risk_analysis

def test_assign_risk_tier_red(make_pr):
    """PR with last activity 6 days ago should be RED."""
    pr = make_pr(last_activity_at=datetime.utcnow() - timedelta(days=6))
    assert assign_risk_tier(pr) == "red"

def test_assign_risk_tier_amber(make_pr):
    """PR with last activity 3 days ago should be AMBER."""
    pr = make_pr(last_activity_at=datetime.utcnow() - timedelta(days=3))
    assert assign_risk_tier(pr) == "amber"

def test_assign_risk_tier_green(make_pr):
    """PR with last activity 1 hour ago should be GREEN."""
    pr = make_pr(last_activity_at=datetime.utcnow() - timedelta(hours=1))
    assert assign_risk_tier(pr) == "green"

def test_detect_stall_reason_ci_failing(make_pr):
    """Should return 'ci_failing' if combined status or check runs indicates failure."""
    pr = make_pr()
    reviews = []
    comments = []
    
    # Combined status failure
    ci_status = {"state": "failure"}
    reason = detect_stall_reason(pr, reviews, comments, ci_status)
    assert reason == "ci_failing"
    
    # Check runs failure
    ci_status_check = {
        "check_runs": [
            {"conclusion": "success"},
            {"conclusion": "failure"}
        ]
    }
    reason = detect_stall_reason(pr, reviews, comments, ci_status_check)
    assert reason == "ci_failing"

def test_detect_stall_reason_waiting_on_author(make_pr):
    """Should return 'waiting_on_author' if latest review action is CHANGES_REQUESTED."""
    pr = make_pr()
    reviews = [
        {"state": "APPROVED", "submitted_at": "2026-06-25T10:00:00Z"},
        {"state": "CHANGES_REQUESTED", "submitted_at": "2026-06-25T12:00:00Z"}
    ]
    comments = []
    ci_status = None
    reason = detect_stall_reason(pr, reviews, comments, ci_status)
    assert reason == "waiting_on_author"

def test_run_risk_analysis_updates_and_clears_for_green(make_pr):
    """run_risk_analysis should assign green risk tier and clear stall_reason."""
    # Stalled PR that gets updated and becomes green
    pr = make_pr(
        last_activity_at=datetime.utcnow() - timedelta(hours=1),
        risk_tier=RiskTier.RED,
        stall_reason="ci_failing"
    )
    reviews = []
    comments = []
    ci_status = None
    
    updated_pr = run_risk_analysis(pr, reviews, comments, ci_status)
    assert updated_pr.risk_tier == RiskTier.GREEN
    assert updated_pr.stall_reason is None
