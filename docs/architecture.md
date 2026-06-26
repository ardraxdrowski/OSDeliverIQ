# OSDeliverIQ System Architecture

This document describes the high-level architecture, component design, and data flows of OSDeliverIQ.

## System Components

OSDeliverIQ is structured into modular components:

1. **FastAPI Web Application (`src/main.py` & `src/api/`)**
   - Serves as the web entry point and exposes user routes (for UI dashboards) and API routes (for repository registration, syncing, and risk auditing).
   - Serves server-side rendered HTML using Jinja2 templates.

2. **Database Schema (`src/models.py` & `src/database.py`)**
   - Structured relational models stored in PostgreSQL. 
   - Tracks `repositories`, `pull_requests`, `contributors`, `risk_events`, and `weekly_digests`.

3. **Ingestion Engine (`src/ingestion/`)**
   - **GitHub Client (`github_client.py`)**: An asynchronous client built on `httpx` containing rate-limit handling (403), repository checks (404), and fetchers for pull requests, reviews, comments, and CI/CD status.
   - **Normaliser (`normaliser.py`)**: Map parser converting API JSON dictionaries to SQLAlchemy class models.
   - **Scheduler (`scheduler.py`)**: Uses `APScheduler` to run periodic checks on all registered repositories.

4. **Analytics Suite (`src/analytics/`)**
   - **Risk Engine (`risk_engine.py`)**: Computes activity latency and classifies pull requests into risk tiers (Green, Amber, Red). Pinpoints stall root-causes (e.g. CI failures, missing reviews, unresponsive reviewers, or author revisions).
   - **Cycle Time Engine (`cycle_time.py`)**: Computes lead time for merged pull requests and activity latency metrics.
   - **Contributor Engine (`contributor.py`)**: Analyzes workload metrics and assigns review response tiers.

5. **AI Summarizer & Digest Generator (`src/ai/`)**
   - **Summariser (`summariser.py`)**: Harnesses Claude API (`claude-sonnet-4-6`) to generate brief blocker summaries.
   - **Digest Generator (`digest.py`)**: Converts a week's worth of PR metrics into structured Markdown weekly status reports.

---

## Data Flow

```
[GitHub API]
     │
     ▼ (httpx Async HTTP)
[Ingestion Engine (github_client.py)]
     │
     ▼ (normaliser.py)
[Database (PostgreSQL)] ◄───► [Analytics & Risk Engine (risk_engine.py)]
     │                                    │
     │                                    ▼ (stalled/amber/red PRs)
     │                          [Claude API (summariser / digest)]
     │                                    │
     ▼                                    ▼
[Jinja2 Template Views] ◄────────[FastAPI Routes]
     │
     ▼
[Dashboard UI]
```

### 1. Ingestion Step
- The user inputs a GitHub URL (e.g., `https://github.com/org/repo`) on the dashboard.
- FastAPI parses the URL, records a new `Repository` entity in the DB, and invokes an immediate asynchronous ingestion job.
- The Ingestion Engine queries GitHub endpoints to fetch repository details and all pull request timelines.

### 2. Processing and Normalization Step
- Raw JSON representations are parsed by the `Normaliser`.
- Repository, Pull Request, and Contributor states are updated/inserted. Contributors are cross-referenced using their unique GitHub logins.

### 3. Risk Evaluation & Analysis Step
- The ingestion process triggers the `Risk Engine` for all open pull requests.
- Latencies are calculated. If the PR has no activity for 48 hours, it escalates to Amber; if it exceeds 120 hours, it escalates to Red.
- When an Amber or Red risk is flagged, reviews, commits, checks, and comments are evaluated to determine the stall reason (`no_reviewer_assigned`, `reviewer_unresponsive`, `ci_failing`, `waiting_on_author`, `dependency_blocked`).

### 4. AI Block Summary Step
- If a PR is stalled (Amber or Red), the last 10 comments and the description are extracted.
- The text is dispatched to Claude with a system prompt specifying a 2-sentence constraint. The summary is persisted directly inside `pull_requests.ai_blocker_summary`.

### 5. Weekly Digest Step
- When the user visits the digest page, OSDeliverIQ queries the database for PR activities updated during the trailing week.
- If the Anthropic API is configured, the data is transformed by Claude into accomplishments, risks, decisions, and milestones. If disabled or failing, a structured Python template fallback generates the report dynamically.
- The HTML representation is rendered instantly on the dashboard using a basic regex-free translation.
