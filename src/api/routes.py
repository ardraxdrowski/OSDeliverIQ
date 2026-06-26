import re
import logging
import uuid
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models import Repository, PullRequest, RiskEvent, WeeklyDigest, PRStatus, RiskTier
from src.ingestion.scheduler import sync_repository
from pathlib import Path


logger = logging.getLogger(__name__)
router = APIRouter()

#templates = Jinja2Templates(directory="src/api/templates")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

class RepoCreate(BaseModel):
    github_url: str

def markdown_to_html(md_text: str) -> str:
    """Helper to convert markdown status report to clean styled HTML block without packages."""
    if not md_text:
        return ""
    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        # Headers
        if stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        # Lists
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = stripped[2:]
            # Bold tags replacement **text** -> <strong>text</strong>
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
            html_lines.append(f"<li>{content}</li>")
        # Empty Line
        elif not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<br>")
        # Regular text paragraphs
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            content = stripped
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
            html_lines.append(f"<p>{content}</p>")
            
    if in_list:
        html_lines.append("</ul>")
        
    return "\n".join(html_lines)

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Render dashboard page listing all repositories and their health scores."""
    result = await db.execute(select(Repository))
    repositories = result.scalars().all()
    
    enriched_repos = []
    for repo in repositories:
        # Fetch PRs for each repository
        prs_result = await db.execute(
            select(PullRequest).where(PullRequest.repo_id == repo.id)
        )
        prs = prs_result.scalars().all()
        
        # Calculate counts
        open_prs = [pr for pr in prs if pr.status == PRStatus.OPEN]
        red_count = len([pr for pr in open_prs if pr.risk_tier == RiskTier.RED])
        amber_count = len([pr for pr in open_prs if pr.risk_tier == RiskTier.AMBER])
        
        # Health score logic
        health_score = 100 - (red_count * 20) - (amber_count * 5)
        health_score = max(0, health_score)
        
        enriched_repos.append({
            "id": repo.id,
            "name": repo.name,
            "github_url": repo.github_url,
            "last_synced_at": repo.last_synced_at,
            "open_prs_count": len(open_prs),
            "red_count": red_count,
            "amber_count": amber_count,
            "health_score": health_score
        })

    '''return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "repos": enriched_repos}
    '''
    return templates.TemplateResponse(
    request=request,
    name="dashboard.html",
    context={
        "request": request,
        "repos": enriched_repos,
    },
)
    


@router.get("/repo/{repo_id}", response_class=HTMLResponse)
async def get_repo_detail(repo_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Render repository details and PRs sorted by risk tier."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    prs_result = await db.execute(
        select(PullRequest).where(PullRequest.repo_id == repo_id)
    )
    prs = prs_result.scalars().all()
    
    open_prs = [pr for pr in prs if pr.status == PRStatus.OPEN]
    red_count = len([pr for pr in open_prs if pr.risk_tier == RiskTier.RED])
    amber_count = len([pr for pr in open_prs if pr.risk_tier == RiskTier.AMBER])
    
    health_score = 100 - (red_count * 20) - (amber_count * 5)
    health_score = max(0, health_score)

    now = datetime.utcnow()
    # Sort: Open first (by risk: red, amber, green), then merged/closed
    for pr in prs:
        pr.days_stalled = (now - pr.last_activity_at).total_seconds() / 86400.0

    def sort_key(pr):
        # Open: red=0, amber=1, green=2. Closed/Merged=3
        if pr.status == PRStatus.OPEN:
            return {"red": 0, "amber": 1, "green": 2}.get(pr.risk_tier.value, 3)
        return 3

    sorted_prs = sorted(prs, key=sort_key)

    return templates.TemplateResponse(
        request=request,
        name="repo_detail.html",
        context={
            "request": request,
            "repo": repo,
            "prs": sorted_prs,
            "health_score": health_score,
            "open_count": len(open_prs),
            "red_count": red_count,
            "amber_count": amber_count
        }
    )

@router.get("/repo/{repo_id}/pr/{pr_id}", response_class=HTMLResponse)
async def get_pr_detail(repo_id: uuid.UUID, pr_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Render pull request detail page, including AI blocker summary and risk history."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    pr_result = await db.execute(
        select(PullRequest)
        .options(selectinload(PullRequest.risk_events))
        .where(PullRequest.id == pr_id)
    )
    pr = pr_result.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")

    now = datetime.utcnow()
    pr.days_stalled = (now - pr.last_activity_at).total_seconds() / 86400.0

    return templates.TemplateResponse(
        request=request,
        name="pr_detail.html",
        context={
            "request": request,
            "repo": repo,
            "pr": pr
        }
    )

@router.get("/repo/{repo_id}/digest", response_class=HTMLResponse)
async def get_latest_digest(repo_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Render the latest weekly status report (digest) in HTML. Generates one if it doesn't exist."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    digest_result = await db.execute(
        select(WeeklyDigest)
        .where(WeeklyDigest.repo_id == repo_id)
        .order_by(WeeklyDigest.week_start.desc())
    )
    digest = digest_result.scalar_one_or_none()
    
    if not digest:
        # Generate new digest for the current week starting Monday
        from datetime import date, timedelta
        from src.ai.digest import generate_digest
        from src.analytics.cycle_time import calculate_cycle_time
        
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        # Get PRs updated in last 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        prs_result = await db.execute(
            select(PullRequest).where(
                PullRequest.repo_id == repo_id,
                PullRequest.last_activity_at >= seven_days_ago
            )
        )
        prs = prs_result.scalars().all()
        
        week_prs = []
        for pr in prs:
            cycle_time = calculate_cycle_time(pr)
            week_prs.append({
                "title": pr.title,
                "status": pr.status.value,
                "risk_tier": pr.risk_tier.value,
                "stall_reason": pr.stall_reason,
                "cycle_time_hours": cycle_time
            })
            
        digest_md = await generate_digest(repo.name, week_prs)
        
        digest = WeeklyDigest(
            repo_id=repo_id,
            week_start=week_start,
            markdown_content=digest_md,
            generated_at=datetime.utcnow()
        )
        db.add(digest)
        await db.commit()
        await db.refresh(digest)

    html_content = markdown_to_html(digest.markdown_content)

    return templates.TemplateResponse(
        request=request,
        name="digest.html",
        context={
            "request": request,
            "repo": repo,
            "digest": digest,
            "html_content": html_content
        }
    )

@router.post("/api/repos", status_code=status.HTTP_201_CREATED)
async def add_repository(payload: RepoCreate, db: AsyncSession = Depends(get_db)):
    """Add a new GitHub repository to track and trigger a first-time sync."""
    github_url = payload.github_url.strip()
    
    # Parse owner and repo name from github URL
    match = re.search(r"github\.com/([^/]+)/([^/]+)", github_url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
        
    owner = match.group(1)
    repo_name = match.group(2).replace(".git", "")
    full_name = f"{owner}/{repo_name}"

    # Check if already tracked
    existing_result = await db.execute(
        select(Repository).where(Repository.name == full_name)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Repository is already being tracked")

    new_repo = Repository(
        name=full_name,
        github_url=f"https://github.com/{full_name}",
        github_owner=owner,
        github_repo=repo_name,
        tracked_since=datetime.utcnow()
    )
    
    db.add(new_repo)
    await db.commit()
    await db.refresh(new_repo)

    # Trigger immediate sync
    try:
        await sync_repository(new_repo.id)
    except Exception as e:
        logger.error(f"First sync failed for {full_name}: {e}", exc_info=True)
        # Continue and return 201; background sync will retry.

    return {"status": "created", "repo_id": new_repo.id}

@router.post("/api/repos/{repo_id}/sync")
async def trigger_sync(repo_id: uuid.UUID):
    """Trigger manual repository synchronisation immediately."""
    try:
        await sync_repository(repo_id)
        return {"status": "success", "message": "Synchronisation triggered and completed"}
    except Exception as e:
        logger.error(f"Manual sync failed for ID {repo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/repos/{repo_id}/risk")
async def get_risk_events(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return all risk events for pull requests in the repository as JSON."""
    result = await db.execute(
        select(RiskEvent)
        .join(PullRequest)
        .where(PullRequest.repo_id == repo_id)
        .order_by(RiskEvent.detected_at.desc())
    )
    events = result.scalars().all()
    
    return [
        {
            "id": str(event.id),
            "pr_id": str(event.pr_id),
            "event_type": event.event_type,
            "detected_at": event.detected_at.isoformat(),
            "summary_text": event.summary_text,
            "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None
        }
        for event in events
    ]

@router.get("/health")
async def health_check():
    """Simple API health check endpoint."""
    return {"status": "ok"}
