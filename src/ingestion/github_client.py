import logging
from typing import Any, Dict, List, Optional
import httpx
from src.config import settings

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "OSDeliverIQ"
        }
        if settings.GITHUB_TOKEN:
            # GitHub accepts both "token TOKEN" and "Bearer TOKEN"
            self.headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"
        
        self.base_url = "https://api.github.com"
        self.timeout = 10.0

    async def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, params=params, json=json_body)
                
                # Check status
                if response.status_code == 403:
                    logger.warning(f"GitHub API 403 Rate Limit / Forbidden on {url}: {response.text}")
                    return [] if "comments" in path or "pulls" in path or "commits" in path or "reviews" in path else None
                elif response.status_code == 404:
                    logger.warning(f"GitHub API 404 Not Found on {url}")
                    return [] if "comments" in path or "pulls" in path or "commits" in path or "reviews" in path else None
                
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Network request error occurred: {e}")
                raise

    async def get_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata for a repository."""
        path = f"/repos/{owner}/{repo}"
        result = await self._request("GET", path)
        if isinstance(result, list): # Fallback returned from 403/404 handling
            return None
        return result

    async def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        """List pull requests for a repository."""
        path = f"/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": 100}
        result = await self._request("GET", path, params=params)
        return result if isinstance(result, list) else []

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed information for a specific pull request."""
        path = f"/repos/{owner}/{repo}/pulls/{pr_number}"
        result = await self._request("GET", path)
        if isinstance(result, list): # Fallback returned from 403/404 handling
            return None
        return result

    async def get_pr_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch the last 10 comments (issue comments) sorted by created_at descending."""
        path = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
        params = {
            "sort": "created",
            "direction": "desc",
            "per_page": 10
        }
        result = await self._request("GET", path, params=params)
        return result if isinstance(result, list) else []

    async def get_pr_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch reviews for a pull request."""
        path = f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        result = await self._request("GET", path)
        return result if isinstance(result, list) else []

    async def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch commits for a pull request."""
        path = f"/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        params = {"per_page": 50}
        result = await self._request("GET", path, params=params)
        return result if isinstance(result, list) else []

    async def get_commit_status(self, owner: str, repo: str, ref: str) -> Optional[Dict[str, Any]]:
        """Fetch combined status for a commit SHA/ref."""
        path = f"/repos/{owner}/{repo}/commits/{ref}/status"
        result = await self._request("GET", path)
        if isinstance(result, list):
            return None
        return result

    async def get_commit_check_runs(self, owner: str, repo: str, ref: str) -> List[Dict[str, Any]]:
        """Fetch check runs for a commit SHA/ref."""
        path = f"/repos/{owner}/{repo}/commits/{ref}/check-runs"
        result = await self._request("GET", path)
        if isinstance(result, dict) and "check_runs" in result:
            return result["check_runs"]
        return []
