"""Web search tool using Brave Search API."""

import httpx

from sentinel.core.types import ActionResult
from sentinel.tools.base import RiskLevel, tool
from sentinel.tools.registry import register_tool

# Global state - initialized during startup
_brave_api_key: str = ""


def set_brave_api_key(api_key: str) -> None:
    """Set Brave Search API key (called during initialization)."""
    global _brave_api_key
    _brave_api_key = api_key


@tool(
    "web_search",
    "Search the web for current information using Brave Search",
    risk_level=RiskLevel.LOW,
    examples=[
        'web_search("latest news about AI")',
        'web_search("weather in Tokyo", count=5)',
    ],
)
async def web_search(query: str, count: int = 5) -> ActionResult:
    """
    Search the web using Brave Search API.

    query: Search query string
    count: Number of results to return (1-20, default 5)

    Returns:
        ActionResult with search results (title, url, description)
    """
    if not _brave_api_key:
        return ActionResult(
            success=False,
            error="Brave Search API key not configured. Set SENTINEL_BRAVE_SEARCH_API_KEY in .env",
        )

    # Validate count parameter
    count = max(1, min(20, count))

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": _brave_api_key,
    }
    params = {
        "q": query,
        "count": count,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Extract web results
            web_results = data.get("web", {}).get("results", [])

            if not web_results:
                return ActionResult(
                    success=True,
                    data={
                        "query": query,
                        "results": [],
                        "message": "No results found",
                    },
                )

            # Format results
            results = []
            for result in web_results[:count]:
                results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "description": result.get("description", ""),
                    }
                )

            return ActionResult(
                success=True,
                data={
                    "query": query,
                    "count": len(results),
                    "results": results,
                },
            )

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
        if e.response.status_code == 401:
            error_msg = "Invalid Brave Search API key"
        elif e.response.status_code == 429:
            error_msg = "Rate limit exceeded for Brave Search API"

        return ActionResult(success=False, error=error_msg)

    except httpx.TimeoutException:
        return ActionResult(success=False, error="Search request timed out")

    except Exception as e:
        return ActionResult(success=False, error=f"Search failed: {e!s}")


@tool(
    "fetch_webpage",
    "Fetch and parse webpage content into clean, AI-readable format",
    risk_level=RiskLevel.LOW,
    examples=[
        'fetch_webpage("https://example.com")',
        'fetch_webpage("https://news.site/article", format="json")',
    ],
)
async def fetch_webpage(url: str, format: str = "markdown") -> ActionResult:
    """
    Fetch webpage content using Jina AI Reader service.

    url: Target webpage URL to fetch
    format: Output format - "markdown" (default) or "json"

    Returns:
        ActionResult with parsed webpage content
    """
    # Validate URL format
    if not url.startswith(("http://", "https://")):
        return ActionResult(
            success=False,
            error="URL must start with http:// or https://",
        )

    # Validate format parameter
    if format not in ("markdown", "json"):
        format = "markdown"

    # Construct Jina AI Reader URL
    jina_url = f"https://r.jina.ai/{url}"

    headers = {
        "Accept": "application/json" if format == "json" else "text/markdown",
        "X-Return-Format": format,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(jina_url, headers=headers)
            response.raise_for_status()

            # Extract content based on format
            if format == "json":
                data = response.json()
                content = data.get("data", {}).get("content", response.text)
                title = data.get("data", {}).get("title", "")
                description = data.get("data", {}).get("description", "")

                return ActionResult(
                    success=True,
                    data={
                        "url": url,
                        "format": format,
                        "title": title,
                        "description": description,
                        "content": content,
                    },
                )
            else:
                # Markdown format
                content = response.text
                return ActionResult(
                    success=True,
                    data={
                        "url": url,
                        "format": format,
                        "content": content,
                    },
                )

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: Failed to fetch webpage"
        if e.response.status_code == 404:
            error_msg = "Webpage not found (404)"
        elif e.response.status_code == 403:
            error_msg = "Access forbidden (403)"
        elif e.response.status_code == 500:
            error_msg = "Server error (500)"

        return ActionResult(success=False, error=error_msg)

    except httpx.TimeoutException:
        return ActionResult(success=False, error="Request timed out after 30 seconds")

    except httpx.InvalidURL:
        return ActionResult(success=False, error="Invalid URL format")

    except Exception as e:
        return ActionResult(success=False, error=f"Failed to fetch webpage: {e!s}")


def register_web_search_tools() -> None:
    """Register web search tools with the global registry."""
    register_tool(web_search._tool)  # type: ignore[attr-defined]
    register_tool(fetch_webpage._tool)  # type: ignore[attr-defined]
