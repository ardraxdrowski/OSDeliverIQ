import httpx
import pytest
from unittest.mock import AsyncMock, patch
from src.ingestion.github_client import GitHubClient

@pytest.mark.asyncio
async def test_list_pull_requests_403_rate_limit():
    """list_pull_requests should handle HTTP 403 rates limits, log a warning, and return an empty list."""
    mock_response = httpx.Response(
        status_code=403,
        json={"message": "API rate limit exceeded"},
        request=httpx.Request("GET", "https://api.github.com/repos/owner/repo/pulls")
    )
    
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        client = GitHubClient()
        prs = await client.list_pull_requests("owner", "repo")
        
        assert prs == []
        # Check that we requested the pulls endpoint
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert "/repos/owner/repo/pulls" in args[1]

@pytest.mark.asyncio
async def test_get_repository_404_not_found():
    """get_repository should handle HTTP 404 not found, log a warning, and return None."""
    mock_response = httpx.Response(
        status_code=404,
        json={"message": "Not Found"},
        request=httpx.Request("GET", "https://api.github.com/repos/owner/repo")
    )
    
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        client = GitHubClient()
        repo = await client.get_repository("owner", "repo")
        
        assert repo is None
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert "/repos/owner/repo" in args[1]
