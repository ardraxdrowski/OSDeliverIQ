import uuid
from datetime import datetime, date
from enum import Enum
from typing import List, Optional

from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Enum as SQLEnum, Uuid, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

class PRStatus(str, Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"

class RiskTier(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    github_url: Mapped[str] = mapped_column(String, nullable=False)
    github_owner: Mapped[str] = mapped_column(String, nullable=False)
    github_repo: Mapped[str] = mapped_column(String, nullable=False)
    tracked_since: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )
    weekly_digests: Mapped[List["WeeklyDigest"]] = relationship(
        "WeeklyDigest", back_populates="repository", cascade="all, delete-orphan"
    )

class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    github_login: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timezone_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_response_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_prs_reviewed: Mapped[int] = mapped_column(Integer, default=0)

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author_login: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Status and risk tier enums
    status: Mapped[PRStatus] = mapped_column(SQLEnum(PRStatus), nullable=False)
    risk_tier: Mapped[RiskTier] = mapped_column(SQLEnum(RiskTier), default=RiskTier.GREEN, nullable=False)
    
    stall_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_blocker_summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    risk_events: Mapped[List["RiskEvent"]] = relationship(
        "RiskEvent", back_populates="pull_request", cascade="all, delete-orphan"
    )

class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pr_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "stall_detected", "reviewer_unresponsive"
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="risk_events")

class WeeklyDigest(Base):
    __tablename__ = "weekly_digests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="weekly_digests")
