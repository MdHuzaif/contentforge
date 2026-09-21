"""TDD tests for Tavily primary search source."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_tavily_returns_normalized_results(monkeypatch):
    """Tavily JSON must be normalized to {title, url, snippet}."""
    import asyncio
    from backend.tools import web_search as ws
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value={
        "results": [
            {"title": "A", "url": "https://a.com", "content": "snippet A", "score": 0.9},
            {"title": "B", "url": "https://b.com", "content": "snippet B", "score": 0.8},
        ]
    })

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.tools.web_search.httpx.AsyncClient", return_value=fake_client):
        results = asyncio.run(ws.search_tavily("test query", 5))

    assert len(results) == 2
    assert results[0]["url"] == "https://a.com"
    assert results[0]["snippet"] == "snippet A"
    # Verify basic depth used (1 credit, not 2)
    call_kwargs = fake_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert body.get("search_depth") == "basic"


def test_tavily_skips_without_key(monkeypatch):
    """No TAVILY_API_KEY → return [] silently, no HTTP call."""
    import asyncio
    from backend.tools import web_search as ws
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch("backend.tools.web_search.httpx.AsyncClient") as mock_client:
        results = asyncio.run(ws.search_tavily("q", 5))
    assert results == []
    mock_client.assert_not_called()


def test_tavily_site_query_converts_to_include_domains(monkeypatch):
    """'site:reddit.com X' must become include_domains=['reddit.com']."""
    import asyncio
    from backend.tools import web_search as ws
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value={"results": []})

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.tools.web_search.httpx.AsyncClient", return_value=fake_client):
        asyncio.run(ws.search_tavily("site:reddit.com best laptops", 5))

    body = fake_client.post.call_args.kwargs.get("json")
    assert body.get("include_domains") == ["reddit.com"]
    assert "site:" not in body.get("query", "")


def test_tavily_error_returns_empty(monkeypatch):
    """Network/HTTP errors must return [] not raise."""
    import asyncio
    import httpx as httpx_lib
    from backend.tools import web_search as ws
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=httpx_lib.TimeoutException("timeout"))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.tools.web_search.httpx.AsyncClient", return_value=fake_client):
        results = asyncio.run(ws.search_tavily("q", 5))
    assert results == []


def test_get_top_results_tries_tavily_first(monkeypatch):
    """get_top_results chain must be: Tavily → DDG → DDG Lite → Bing."""
    import asyncio
    from backend.tools import web_search as ws
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")

    order = []
    async def fake_tavily(q, max_results=10, n=10, **kwargs):
        order.append("tavily")
        return [{"title": "T", "url": "https://t.com", "snippet": "s"}]
    async def fake_ddg(q, max_results=10, n=10, **kwargs):
        order.append("ddg")
        return []
    async def fake_lite(q, max_results=6, n=6, **kwargs):
        order.append("lite")
        return []
    async def fake_bing(q, max_results=10, n=10, **kwargs):
        order.append("bing")
        return []

    monkeypatch.setattr(ws, "search_tavily", fake_tavily)
    monkeypatch.setattr(ws, "search_duckduckgo", fake_ddg)
    monkeypatch.setattr(ws, "search_ddg_lite", fake_lite)
    monkeypatch.setattr(ws, "search_bing", fake_bing)

    results = asyncio.run(ws.get_top_results("query", 5))
    assert len(results) == 1
    assert order == ["tavily"], f"Expected tavily first, got {order}"


def test_get_top_results_falls_back_when_tavily_empty(monkeypatch):
    """If Tavily returns [], DDG must be tried next."""
    import asyncio
    from backend.tools import web_search as ws
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")

    order = []
    async def fake_tavily(q, max_results=10, n=10, **kwargs):
        order.append("tavily")
        return []
    async def fake_ddg(q, max_results=10, n=10, **kwargs):
        order.append("ddg")
        return [{"title": "D", "url": "https://d.com", "snippet": "s"}]
    async def fake_lite(q, max_results=6, n=6, **kwargs):
        order.append("lite")
        return []
    async def fake_bing(q, max_results=10, n=10, **kwargs):
        order.append("bing")
        return []

    monkeypatch.setattr(ws, "search_tavily", fake_tavily)
    monkeypatch.setattr(ws, "search_duckduckgo", fake_ddg)
    monkeypatch.setattr(ws, "search_ddg_lite", fake_lite)
    monkeypatch.setattr(ws, "search_bing", fake_bing)

    results = asyncio.run(ws.get_top_results("query", 5))
    assert len(results) == 1
    assert order == ["tavily", "ddg"]
