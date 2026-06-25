import os
from dotenv import load_dotenv

# Load env file if it exists
load_dotenv()

class Settings:
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:password@db:5432/osdeliveriq"
    )
    POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))
    STALL_RED_HOURS: int = int(os.getenv("STALL_RED_HOURS", "120"))
    STALL_AMBER_HOURS: int = int(os.getenv("STALL_AMBER_HOURS", "48"))

settings = Settings()
