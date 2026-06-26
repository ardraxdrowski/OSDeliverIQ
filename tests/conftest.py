import pytest
import uuid
from datetime import datetime, timedelta
from src.models import PullRequest, PRStatus, RiskTier

@pytest.fixture
def make_pr():
    """Fixture that returns a factory function to build PullRequest objects with configurable datetimes and statuses."""
    def _make_pr(
        last_activity_at: datetime = None,
        created_at: datetime = None,
        status: PRStatus = PRStatus.OPEN,
        risk_tier: RiskTier = RiskTier.GREEN,
        stall_reason: str = None,
        title: str = "Test PR",
        author_login: str = "author1",
        merged_at: datetime = None,
        closed_at: datetime = None
    ) -> PullRequest:
        now = datetime.utcnow()
        if last_activity_at is None:
            last_activity_at = now
        if created_at is None:
            created_at = last_activity_at - timedelta(days=1)
       
        return PullRequest(
            id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            github_pr_number=101,
            title=title,
            author_login=author_login,
            created_at=created_at,
            last_activity_at=last_activity_at,
            status=status,
            risk_tier=risk_tier,
            stall_reason=stall_reason,
            merged_at=merged_at,
            closed_at=closed_at
        )
    return _make_pr
     # "# rel: async session fixture reserved for integration tests"