from datetime import datetime
from typing import Any, Dict, Optional
from src.models import Repository, PullRequest, Contributor, PRStatus, RiskTier

def parse_github_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # GitHub API returns UTC datetime as "YYYY-MM-DDTHH:MM:SSZ"
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

def normalize_repository(repo_data: Dict[str, Any]) -> Repository:
    """Convert raw GitHub repository API response to a Repository model."""
    full_name = repo_data.get("full_name", "")
    parts = full_name.split("/")
    owner = parts[0] if len(parts) > 0 else ""
    repo_name = parts[1] if len(parts) > 1 else ""

    return Repository(
        name=full_name,
        github_url=repo_data.get("html_url", ""),
        github_owner=owner,
        github_repo=repo_name,
        tracked_since=datetime.utcnow(),
        last_synced_at=None
    )

def normalize_pull_request(pr_data: Dict[str, Any], repo_id: Any) -> PullRequest:
    """Convert raw GitHub pull request API response to a PullRequest model."""
    # Determine PR status
    state = pr_data.get("state", "open")
    merged_at_str = pr_data.get("merged_at")
    closed_at_str = pr_data.get("closed_at")
    
    merged_at = parse_github_datetime(merged_at_str)
    closed_at = parse_github_datetime(closed_at_str)

    if merged_at:
        status = PRStatus.MERGED
    elif closed_at:
        status = PRStatus.CLOSED
    else:
        status = PRStatus.OPEN

    # Determine author
    user = pr_data.get("user") or {}
    author_login = user.get("login", "unknown")

    return PullRequest(
        repo_id=repo_id,
        github_pr_number=pr_data.get("number", 0),
        title=pr_data.get("title", ""),
        author_login=author_login,
        created_at=parse_github_datetime(pr_data.get("created_at")) or datetime.utcnow(),
        last_activity_at=parse_github_datetime(pr_data.get("updated_at")) or datetime.utcnow(),
        merged_at=merged_at,
        closed_at=closed_at,
        status=status,
        risk_tier=RiskTier.GREEN,
        stall_reason=None,
        ai_blocker_summary=None
    )

def normalize_contributor(user_data: Dict[str, Any]) -> Contributor:
    """Convert raw GitHub user API response to a Contributor model."""
    return Contributor(
        github_login=user_data.get("login", ""),
        display_name=user_data.get("name") or user_data.get("login", ""),
        timezone_offset=None,
        avg_response_hours=None,
        total_prs_reviewed=0
    )
