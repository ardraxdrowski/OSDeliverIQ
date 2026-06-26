import logging
from datetime import datetime
from typing import Any, Dict, List
import anthropic
from src.config import settings

logger = logging.getLogger(__name__)

def generate_fallback_digest(repo_name: str, week_prs: List[Dict[str, Any]]) -> str:
    """Generates a plain templated markdown status report from the PR data when API calls fail or are disabled."""
    merged_prs = [pr for pr in week_prs if pr.get("status") == "merged"]
    closed_prs = [pr for pr in week_prs if pr.get("status") == "closed"]
    open_prs = [pr for pr in week_prs if pr.get("status") == "open"]
    
    stalled_prs = [pr for pr in open_prs if pr.get("risk_tier") in ("red", "amber")]
    
    # 1. Accomplishments
    accomplishments = []
    if merged_prs:
        accomplishments.append("### Merged Pull Requests:")
        for pr in merged_prs:
            cycle_time = pr.get("cycle_time_hours")
            cycle_str = f" (Cycle Time: {cycle_time:.1f} hours)" if cycle_time is not None else ""
            accomplishments.append(f"- **{pr.get('title')}**{cycle_str}")
    if closed_prs:
        accomplishments.append("### Closed Pull Requests:")
        for pr in closed_prs:
            accomplishments.append(f"- **{pr.get('title')}** (Closed)")
    if not accomplishments:
        accomplishments.append("- No pull requests were merged or closed this week.")

    # 2. Active risks
    risks = []
    if stalled_prs:
        for pr in stalled_prs:
            reason = pr.get("stall_reason") or "unspecified reason"
            risks.append(f"- **{pr.get('title')}** is flagged **{pr.get('risk_tier').upper()}** tier. Reason: {reason.replace('_', ' ')}.")
    else:
        risks.append("- No immediate delivery risks detected. All open pull requests are in the GREEN tier.")

    # 3. Decisions needed
    decisions = []
    if stalled_prs:
        decisions.append("- Review active risks and reassign reviewers or contact authors for stalled PRs:")
        for pr in stalled_prs:
            decisions.append(f"  - Action required on stalled PR: *{pr.get('title')}*")
    else:
        decisions.append("- None. No blocked or high-risk development paths identified.")

    # 4. Upcoming milestones
    milestones = []
    active_open = [pr for pr in open_prs if pr.get("risk_tier") == "green"]
    if active_open:
        milestones.append("- Drive remaining open PRs towards merge:")
        for pr in active_open:
            milestones.append(f"  - Target review and merge of: *{pr.get('title')}*")
    else:
        milestones.append("- Clear the current backlog and prepare for next cycle updates.")

    report = (
        f"# Weekly Status Report for {repo_name}\n"
        f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (Fallback Template)\n\n"
        f"## Accomplishments\n" + "\n".join(accomplishments) + "\n\n"
        f"## Active risks\n" + "\n".join(risks) + "\n\n"
        f"## Decisions needed\n" + "\n".join(decisions) + "\n\n"
        f"## Upcoming milestones\n" + "\n".join(milestones)
    )
    return report

async def generate_digest(repo_name: str, week_prs: List[Dict[str, Any]]) -> str:
    """Generates a weekly markdown status report for a repository using Anthropic's Claude API.
    
    If settings.ANTHROPIC_API_KEY is missing or the call fails, returns a local fallback markdown report.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not set. Generating fallback digest.")
        return generate_fallback_digest(repo_name, week_prs)

    try:
        # Format the PR activity for Claude
        pr_lines = []
        for pr in week_prs:
            cycle_time = pr.get("cycle_time_hours")
            cycle_str = f", cycle_time: {cycle_time:.1f}h" if cycle_time is not None else ""
            stall_str = f", stall_reason: {pr.get('stall_reason')}" if pr.get("stall_reason") else ""
            pr_lines.append(
                f"- Title: {pr.get('title')}, Status: {pr.get('status')}, "
                f"Risk Tier: {pr.get('risk_tier')}{cycle_str}{stall_str}"
            )
        
        pr_activity = "\n".join(pr_lines)
        
        prompt_content = (
            f"Repository Name: {repo_name}\n\n"
            f"Pull Request Activity this week:\n{pr_activity}\n"
        )

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=(
                "You are a senior project manager writing a weekly status report "
                "for a distributed engineering team. Be concise. Use bullet points. "
                "Flag risks clearly. Do not pad with filler. You MUST return exactly "
                "four sections with these headers:\n"
                "## Accomplishments\n"
                "## Active risks\n"
                "## Decisions needed\n"
                "## Upcoming milestones"
            ),
            messages=[
                {"role": "user", "content": prompt_content}
            ]
        )
        
        if response.content and len(response.content) > 0:
            return response.content[0].text.strip()
        
        logger.warning("Empty response from Anthropic API. Using fallback digest.")
        return generate_fallback_digest(repo_name, week_prs)

    except Exception as e:
        logger.error(f"Failed to generate digest using Anthropic: {e}. Using fallback.", exc_info=True)
        return generate_fallback_digest(repo_name, week_prs)
