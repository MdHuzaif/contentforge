"""TDD tests: Product freshness validation (block 2024 & older products)."""
import pytest
from datetime import datetime


def test_tavily_accepts_days_param(monkeypatch):
    """search_tavily must pass 'days' to the API body when provided."""
    import asyncio
    from unittest.mock import patch, MagicMock, AsyncMock
    from backend.tools import web_search as ws

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")
    captured = {}

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value={
        "results": [{"title": "T", "url": "https://x.com", "content": "s"}]
    })

    fake_client = AsyncMock()
    async def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return fake_response
    fake_client.post = fake_post
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.tools.web_search.httpx.AsyncClient", return_value=fake_client):
        asyncio.run(ws.search_tavily("best laptops", 5, days=365))

    body = captured["json"]
    assert body.get("days") == 365, f"days param missing: {body}"


def test_tavily_no_days_param_when_not_given(monkeypatch):
    """When days=None, body must NOT include 'days' key."""
    import asyncio
    from unittest.mock import patch, MagicMock, AsyncMock
    from backend.tools import web_search as ws

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")
    captured = {}

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(return_value={"results": []})

    fake_client = AsyncMock()
    async def fake_post(url, **kwargs):
        captured.update(kwargs)
        return fake_response
    fake_client.post = fake_post
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.tools.web_search.httpx.AsyncClient", return_value=fake_client):
        asyncio.run(ws.search_tavily("best laptops", 5))

    body = captured["json"]
    assert "days" not in body


def test_detect_outdated_products():
    """Year-marker detection must flag old products."""
    from core.selectors.product_selector import detect_product_freshness

    # OLD products (2023-2024 markers) -> outdated=True
    assert detect_product_freshness("Apple MacBook Air 15 M3", 2026)["is_outdated"] is True
    assert detect_product_freshness("Dell XPS 14 (2024)", 2026)["is_outdated"] is True
    assert detect_product_freshness("ThinkPad X1 Carbon Gen 12", 2026)["is_outdated"] is True

    # NEW products (2025-2026 markers) -> outdated=False
    assert detect_product_freshness("MacBook Air M4", 2026)["is_outdated"] is False
    assert detect_product_freshness("Dell XPS 14 (2026)", 2026)["is_outdated"] is False
    assert detect_product_freshness("ThinkPad X1 Carbon Gen 13", 2026)["is_outdated"] is False


def test_freshness_flags_products_without_year_marker():
    """Products with NO year marker should be flagged as 'unknown' not auto-rejected."""
    from core.selectors.product_selector import detect_product_freshness

    result = detect_product_freshness("Lenovo IdeaPad Slim 3", 2026)
    assert result["is_outdated"] is False  # unknown != outdated
    assert result["confidence"] in ("unknown", "low")


def test_filter_outdated_products_list():
    """filter_outdated_products must remove old, keep new/unknown."""
    from core.selectors.product_selector import filter_outdated_products

    products = [
        {"name": "MacBook Air M3", "tier": "mid_range", "updated_version_name": "MacBook Air M4"},
        {"name": "MacBook Air M4", "tier": "mid_range"},
        {"name": "Dell XPS 14 (2024)", "tier": "premium", "updated_version_name": "Dell XPS 14 (2026)"},
        {"name": "Dell XPS 14 (2026)", "tier": "premium"},
        {"name": "Lenovo IdeaPad Slim 3", "tier": "budget"},
    ]
    kept, removed = filter_outdated_products(products, current_year=2026)

    kept_names = [p["name"] for p in kept]
    removed_names = [p["name"] for p in removed]

    assert "MacBook Air M4" in kept_names
    assert "Dell XPS 14 (2026)" in kept_names
    assert "Lenovo IdeaPad Slim 3" in kept_names  # unknown kept
    assert "MacBook Air M3" in removed_names
    assert "Dell XPS 14 (2024)" in removed_names


def test_product_year_field_added():
    """Extracted products must carry a product_year field."""
    from core.selectors.product_selector import detect_product_freshness

    assert detect_product_freshness("Dell XPS 14 (2024)", 2026)["detected_year"] == 2024
    assert detect_product_freshness("MacBook Air M4", 2026)["detected_year"] in (2025, 2026)
