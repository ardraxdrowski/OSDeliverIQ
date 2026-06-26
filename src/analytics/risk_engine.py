from datetime import datetime
from typing import Any, Dict, List, Optional
from src.config import settings
from src.models import PullRequest, RiskTier

def assign_risk_tier(pr: PullRequest) -> str:
    """Calculates the hours since the last activity and assigns a risk tier."""
    now = datetime.utcnow()
    hours_since_activity = (now - pr.last_activity_at).total_seconds() / 3600
    
    if hours_since_activity > settings.STALL_RED_HOURS:
        return "red"
    elif hours_since_activity > settings.STALL_AMBER_HOURS:
        return "amber"
    else:
        return "green"

def detect_stall_reason(
    pr: PullRequest, 
    reviews: List[Dict[str, Any]], 
    comments: List[Dict[str, Any]], 
    ci_status: Optional[Dict[str, Any]]
) -> str:
    """Detects why a pull request is stalled based on reviews, comments, and CI status."""
    # 1. Check for dependency block in title, description, or comments
    text_to_check = (pr.title or "").lower()
    if hasattr(pr, "body") and pr.body:
        text_to_check += " " + pr.body.lower()
    
    for comment in comments:
        text_to_check += " " + (comment.get("body") or "").lower()

    if any(phrase in text_to_check for phrase in ["blocked by", "dependency", "depends on"]):
        return "dependency_blocked"

    # 2. Check for CI/check run failures
    if ci_status:
        # Check combined commit status
        if ci_status.get("state") in ("failure", "error"):
            return "ci_failing"
        # Check individual check runs
        check_runs = ci_status.get("check_runs", [])
        if any(run.get("conclusion") == "failure" for run in check_runs):
            return "ci_failing"

    # 3. Check if waiting on author (e.g. Changes Requested is the latest review action)
    sorted_reviews = sorted(reviews, key=lambda r: r.get("submitted_at", ""), reverse=True)
    if sorted_reviews and sorted_reviews[0].get("state") == "CHANGES_REQUESTED":
        return "waiting_on_author"

    # 4. Check for reviewer unresponsiveness or no reviewer assigned
    requested_reviewers = getattr(pr, "requested_reviewers", [])
    
    if not reviews and not requested_reviewers:
        return "no_reviewer_assigned"

    if requested_reviewers and not reviews:
        return "reviewer_unresponsive"

    # If there are reviewers/reviews, check if the author has responded and is waiting
    if comments:
        # Find latest comment
        latest_comment = comments[0] # assuming sorted by created_at desc
        if latest_comment.get("user", {}).get("login") == pr.author_login:
            return "reviewer_unresponsive"

    return "reviewer_unresponsive" if (reviews or requested_reviewers) else "no_reviewer_assigned"

def run_risk_analysis(
    pr: PullRequest, 
    reviews: List[Dict[str, Any]], 
    comments: List[Dict[str, Any]], 
    ci_status: Optional[Dict[str, Any]]
) -> PullRequest:
    """Assigns risk tier and stall reason, updating the PullRequest object."""
    tier = assign_risk_tier(pr)
    pr.risk_tier = RiskTier(tier)
    
    if tier in ("red", "amber"):
        pr.stall_reason = detect_stall_reason(pr, reviews, comments, ci_status)
    else:
        pr.stall_reason = None
        
    return pr
