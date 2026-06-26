import logging
from typing import Any, Dict, List, Optional
import anthropic
from src.config import settings

logger = logging.getLogger(__name__)

async def summarise_blocker(
    pr_title: str, 
    pr_description: Optional[str], 
    comments: List[Any]
) -> Optional[str]:
    """Calls Anthropic Claude API to generate a 2-sentence summary of what is blocking the PR.
    
    Truncates comments to the last 10 (chronological order) before sending.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not set. Returning None for summary.")
        return None

    try:
        # Format the last 10 comments chronologically
        recent_comments = comments[:10]
        recent_comments.reverse() # Reverse from desc to asc (chronological)

        formatted_comments = []
        for c in recent_comments:
            if isinstance(c, dict):
                author = c.get("user", {}).get("login") if isinstance(c.get("user"), dict) else c.get("author_login", "unknown")
                body = c.get("body", "")
                formatted_comments.append(f"[{author}]: {body}")
            else:
                formatted_comments.append(str(c))

        comments_text = "\n".join(formatted_comments)
        description_text = pr_description if pr_description else "No description provided."

        prompt_content = (
            f"PR Title: {pr_title}\n\n"
            f"PR Description:\n{description_text}\n\n"
            f"Recent Comments:\n{comments_text}\n"
        )

        # Using AsyncAnthropic client for non-blocking async calls
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=(
                "You are a technical project manager assistant. Given a GitHub PR "
                "thread, identify and summarise the blocker in exactly 2 sentences. "
                "Be specific. Do not use jargon. Do not speculate."
            ),
            messages=[
                {"role": "user", "content": prompt_content}
            ]
        )
        
        if response.content and len(response.content) > 0:
            return response.content[0].text.strip()
        return None

    except Exception as e:
        logger.error(f"Failed to generate blocker summary using Anthropic: {e}", exc_info=True)
        return None
