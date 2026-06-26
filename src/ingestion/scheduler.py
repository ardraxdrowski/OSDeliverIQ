import logging
import uuid
from datetime import datetime
from sqlalchemy.future import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.database import async_session
from src.models import Repository, PullRequest, Contributor, PRStatus
from src.config import settings
from src.ingestion.github_client import GitHubClient
from src.ingestion.normaliser import normalize_pull_request, normalize_repository, normalize_contributor

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def sync_repository(repo_id: uuid.UUID) -> None:
    """Synchronises a repository's metadata, contributors, and pull requests from GitHub."""
    logger.info(f"Starting sync for repository ID: {repo_id}")
    client = GitHubClient()

    async with async_session() as session:
        # Fetch the repository from the DB
        repo_result = await session.execute(select(Repository).where(Repository.id == repo_id))
        repo = repo_result.scalar_one_or_none()
        if not repo:
            logger.error(f"Repository with ID {repo_id} not found in database.")
            return

        # Fetch repository details from GitHub
        gh_repo_data = await client.get_repository(repo.github_owner, repo.github_repo)
        if not gh_repo_data:
            logger.warning(f"Could not fetch repository {repo.github_owner}/{repo.github_repo} from GitHub.")
            return

        # Update repository details
        repo.name = gh_repo_data.get("full_name", repo.name)
        repo.github_url = gh_repo_data.get("html_url", repo.github_url)
        repo.last_synced_at = datetime.utcnow()

        # Fetch pull requests from GitHub (get both open and closed/merged PRs)
        gh_prs = await client.list_pull_requests(repo.github_owner, repo.github_repo, state="all")
        logger.info(f"Fetched {len(gh_prs)} PRs for {repo.name}")

        for gh_pr in gh_prs:
            # 1. Upsert PR author as contributor
            pr_user = gh_pr.get("user")
            if pr_user and pr_user.get("login"):
                contrib_login = pr_user["login"]
                contrib_result = await session.execute(
                    select(Contributor).where(Contributor.github_login == contrib_login)
                )
                contrib = contrib_result.scalar_one_or_none()
                if not contrib:
                    new_contrib = normalize_contributor(pr_user)
                    session.add(new_contrib)

            # 2. Upsert the Pull Request
            pr_num = gh_pr.get("number")
            pr_result = await session.execute(
                select(PullRequest).where(
                    PullRequest.repo_id == repo.id,
                    PullRequest.github_pr_number == pr_num
                )
            )
            existing_pr = pr_result.scalar_one_or_none()

            normalized_pr = normalize_pull_request(gh_pr, repo.id)

            if existing_pr:
                # Update editable fields
                existing_pr.title = normalized_pr.title
                existing_pr.status = normalized_pr.status
                existing_pr.last_activity_at = normalized_pr.last_activity_at
                existing_pr.merged_at = normalized_pr.merged_at
                existing_pr.closed_at = normalized_pr.closed_at
                # Keep existing risk tiers/AI summaries for now (handled in later steps)
            else:
                session.add(normalized_pr)

        await session.commit()
    logger.info(f"Finished sync for repository ID: {repo_id}")

async def poll_all_repositories() -> None:
    """Trigger sync for all tracked repositories."""
    logger.info("Triggering background sync for all repositories...")
    async with async_session() as session:
        result = await session.execute(select(Repository))
        repos = result.scalars().all()

    for repo in repos:
        try:
            await sync_repository(repo.id)
        except Exception as e:
            logger.error(f"Failed to sync repository {repo.name} (ID: {repo.id}): {e}", exc_info=True)

def start_scheduler() -> None:
    """Starts the APScheduler background jobs."""
    if not scheduler.running:
        scheduler.add_job(
            poll_all_repositories,
            trigger=IntervalTrigger(minutes=settings.POLL_INTERVAL_MINUTES),
            id="poll_all_repos_job",
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Scheduler started. Polling interval: {settings.POLL_INTERVAL_MINUTES} minutes.")

def shutdown_scheduler() -> None:
    """Shuts down the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down.")
