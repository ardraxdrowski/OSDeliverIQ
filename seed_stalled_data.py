import asyncio
import uuid
from datetime import datetime, timedelta, date
from src.database import async_session
from src.models import Repository, PullRequest, RiskEvent, WeeklyDigest, PRStatus, RiskTier, Contributor

async def seed_data():
    print("Connecting to database and seeding mock stalled data...")
    
    async with async_session() as session:
        # 1. Create a mock repository
        repo = Repository(
            id=uuid.uuid4(),
            name="demo-org/stalled-project-demo",
            github_url="https://github.com/demo-org/stalled-project-demo",
            github_owner="demo-org",
            github_repo="stalled-project-demo",
            tracked_since=datetime.utcnow() - timedelta(days=30),
            last_synced_at=datetime.utcnow()
        )
        session.add(repo)
        
        # 2. Add some contributors
        contrib_alice = Contributor(
            github_login="alice-developer",
            display_name="Alice Dev",
            timezone_offset=-5,
            avg_response_hours=4.5,
            total_prs_reviewed=12
        )
        contrib_bob = Contributor(
            github_login="bob-maintainer",
            display_name="Bob Maintainer",
            timezone_offset=1,
            avg_response_hours=49.0, # Will trigger high load warning in contributor.py
            total_prs_reviewed=35
        )
        session.add_all([contrib_alice, contrib_bob])
        
        # 3. Create pull requests with different risk tiers
        
        # Red PR (Stalled 6 days, failing CI)
        pr_red = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo.id,
            github_pr_number=101,
            title="core: fix critical memory leak in packet processing queue",
            author_login="alice-developer",
            created_at=datetime.utcnow() - timedelta(days=12),
            last_activity_at=datetime.utcnow() - timedelta(days=6),
            status=PRStatus.OPEN,
            risk_tier=RiskTier.RED,
            stall_reason="ci_failing",
            ai_blocker_summary="The integration tests are failing on the Ubuntu runner due to an out-of-memory crash. The author needs to optimize the buffer allocations or update the workflow memory limits."
        )
        
        # Amber PR (Stalled 3 days, waiting on author)
        pr_amber = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo.id,
            github_pr_number=102,
            title="db: implement connection pool auto-reconnect logic",
            author_login="bob-maintainer",
            created_at=datetime.utcnow() - timedelta(days=5),
            last_activity_at=datetime.utcnow() - timedelta(days=3),
            status=PRStatus.OPEN,
            risk_tier=RiskTier.AMBER,
            stall_reason="waiting_on_author",
            ai_blocker_summary="Reviewers requested changes on the connection timeouts. The PR is waiting for the author to push updates addressing the feedback."
        )
        
        # Green PR (Active 2 hours ago, healthy)
        pr_green = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo.id,
            github_pr_number=103,
            title="docs: update API endpoints description and specifications",
            author_login="alice-developer",
            created_at=datetime.utcnow() - timedelta(days=1),
            last_activity_at=datetime.utcnow() - timedelta(hours=2),
            status=PRStatus.OPEN,
            risk_tier=RiskTier.GREEN,
            stall_reason=None,
            ai_blocker_summary=None
        )
        
        # Merged PR
        pr_merged = PullRequest(
            id=uuid.uuid4(),
            repo_id=repo.id,
            github_pr_number=98,
            title="auth: support OAuth2 login flow",
            author_login="bob-maintainer",
            created_at=datetime.utcnow() - timedelta(days=15),
            last_activity_at=datetime.utcnow() - timedelta(days=2),
            status=PRStatus.MERGED,
            risk_tier=RiskTier.GREEN,
            merged_at=datetime.utcnow() - timedelta(days=2),
            stall_reason=None,
            ai_blocker_summary=None
        )
        
        session.add_all([pr_red, pr_amber, pr_green, pr_merged])
        
        # 4. Add risk events history for the Red PR
        event1 = RiskEvent(
            pr_id=pr_red.id,
            event_type="stall_detected",
            detected_at=datetime.utcnow() - timedelta(days=6),
            summary_text="PR was flagged in RED risk tier as hours since last activity exceeded 120 hours."
        )
        event2 = RiskEvent(
            pr_id=pr_red.id,
            event_type="ci_failing",
            detected_at=datetime.utcnow() - timedelta(days=6),
            summary_text="GitHub Action 'CI Integration / Test' failed on commit sha a1c3f2d."
        )
        session.add_all([event1, event2])
        
        # 5. Add a weekly digest status report
        digest_md = (
            "## Accomplishments\n"
            "- **auth: support OAuth2 login flow (#98)**: Completed integration of standard security tokens. (Cycle Time: 312.0 hours)\n\n"
            "## Active risks\n"
            "- **core: fix critical memory leak... (#101)** is flagged **RED** tier. Reason: CI failing. Blocker: The integration tests are failing on the Ubuntu runner due to an out-of-memory crash.\n"
            "- **db: implement connection pool... (#102)** is flagged **AMBER** tier. Reason: waiting on author. Blocker: Waiting for author to resolve review comments regarding connection timeouts.\n\n"
            "## Decisions needed\n"
            "- Need decision on memory limit profile adjustments for CI runner machine sizes to resolve #101.\n"
            "- Reassign review of #102 if secondary maintainers need to take over pool sizing validation.\n\n"
            "## Upcoming milestones\n"
            "- Complete documentation updates (#103) and align manuals for the upcoming minor version release."
        )
        
        digest = WeeklyDigest(
            repo_id=repo.id,
            week_start=date.today() - timedelta(days=date.today().weekday()), # Start of this week (Monday)
            markdown_content=digest_md,
            generated_at=datetime.utcnow()
        )
        session.add(digest)
        
        await session.commit()
        
    print(f"\nSuccessfully seeded '{repo.name}' into the database!")
    print("You can now refresh the dashboard at http://localhost:8000 to see it in action.")

if __name__ == "__main__":
    asyncio.run(seed_data())
