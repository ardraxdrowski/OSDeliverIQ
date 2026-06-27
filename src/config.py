import os
from dotenv import load_dotenv

# Load env file if it exists
load_dotenv()

class Settings:
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Railway/Heroku injects DATABASE_URL starting with postgresql://
    # We must replace it with postgresql+asyncpg:// for SQLAlchemy async driver
    _raw_db_url = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:password@db:5432/osdeliveriq"
    )
    if _raw_db_url and _raw_db_url.startswith("postgresql://"):
        DATABASE_URL: str = _raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        DATABASE_URL: str = _raw_db_url

    POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))
    STALL_RED_HOURS: int = int(os.getenv("STALL_RED_HOURS", "120"))
    STALL_AMBER_HOURS: int = int(os.getenv("STALL_AMBER_HOURS", "48"))

settings = Settings()
