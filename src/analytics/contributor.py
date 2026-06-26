from typing import Dict, Any, Optional
from src.models import Contributor

def calculate_contributor_load(contributor: Contributor, open_review_requests: int) -> Dict[str, Any]:
    """Calculates contributor load and returns load tier details."""
    login = contributor.github_login
    open_reviews = open_review_requests
    avg_response_hours = contributor.avg_response_hours
    
    # Default to 0.0 for comparison if average response time is not recorded
    resp_hours = avg_response_hours if avg_response_hours is not None else 0.0

    if open_reviews > 5 or resp_hours > 48:
        load_tier = "high"
    elif open_reviews == 0:
        load_tier = "low"
    else:
        load_tier = "normal"

    return {
        "login": login,
        "open_reviews": open_reviews,
        "avg_response_hours": avg_response_hours,
        "load_tier": load_tier
    }
