"""TDD tests: Firecrawl rescue fetcher (Layer 2) behind httpx (Layer 1)."""
import asyncio

RICH_HTML = (
    "<html><body><article>"
    + "".join(f"<h2>Section {i}</h2><p>" + "word " * 30 + "</p>" for i in range(3))
    + "</article></body></html>"
)
POOR_HTML = "<html><body><div><p>only a few words here</p></div></body></html>"


def test_httpx_success_skips_firecrawl(monkeypatch):
    """Rich httpx HTML must NOT call Firecrawl (save credits)."""
    from backend.tools import content_analyzer as ca
    calls = {"fc": 0}

    async def fake_httpx(url, timeout=15.0):
        return RICH_HTML

    async def fake_fc(url):
        calls["fc"] += 1
        return RICH_HTML

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")

    info = asyncio.run(ca.fetch_and_analyze("https://x.com/a"))
    assert info is not None
    assert info["h2_count"] == 3
    assert calls["fc"] == 0


def test_403_triggers_firecrawl(monkeypatch):
    """httpx None (403) + key set -> firecrawl called, its html analyzed."""
    from backend.tools import content_analyzer as ca
    calls = {"fc": 0}

    async def fake_httpx(url, timeout=15.0):
        return None

    async def fake_fc(url):
        calls["fc"] += 1
        return RICH_HTML

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")

    info = asyncio.run(ca.fetch_and_analyze("https://x.com/a"))
    assert calls["fc"] == 1
    assert info is not None and info["h2_count"] == 3


def test_js_empty_page_triggers_firecrawl(monkeypatch):
    """httpx html with <200 words and 0 h2 -> firecrawl called."""
    from backend.tools import content_analyzer as ca
    calls = {"fc": 0}

    async def fake_httpx(url, timeout=15.0):
        return POOR_HTML

    async def fake_fc(url):
        calls["fc"] += 1
        return RICH_HTML

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")

    info = asyncio.run(ca.fetch_and_analyze("https://x.com/a"))
    assert calls["fc"] == 1
    assert info is not None and info["h2_count"] == 3


def test_no_key_keeps_old_behavior_on_poor_page(monkeypatch):
    """No FIRECRAWL_API_KEY: poor httpx page still analyzed (old behavior)."""
    from backend.tools import content_analyzer as ca
    calls = {"fc": 0}

    async def fake_httpx(url, timeout=15.0):
        return POOR_HTML

    async def fake_fc(url):
        calls["fc"] += 1
        return RICH_HTML

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    info = asyncio.run(ca.fetch_and_analyze("https://x.com/a"))
    assert calls["fc"] == 0
    assert info is not None  # old behavior preserved without key


def test_no_key_all_fail_returns_none(monkeypatch):
    from backend.tools import content_analyzer as ca

    async def fake_httpx(url, timeout=15.0):
        return None

    async def fake_fc(url):
        return RICH_HTML

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    assert asyncio.run(ca.fetch_and_analyze("https://x.com/a")) is None


def test_firecrawl_failure_returns_none(monkeypatch):
    """Both layers fail -> None, never raise."""
    from backend.tools import content_analyzer as ca

    async def fake_httpx(url, timeout=15.0):
        return None

    async def fake_fc(url):
        return None

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")

    assert asyncio.run(ca.fetch_and_analyze("https://x.com/a")) is None


def test_firecrawl_request_shape(monkeypatch):
    """_firecrawl_fetch must send Bearer auth + formats=['html'] to /scrape."""
    from backend.tools import content_analyzer as ca
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test123")
    captured = {}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"success": True,
                    "data": {"html": "<html><body>" + "w " * 300 + "</body></html>"}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(ca.httpx, "AsyncClient", FakeClient)
    html = asyncio.run(ca._firecrawl_fetch("https://x.com/a"))
    assert html and "w w" in html
    assert "firecrawl.dev" in captured["url"]
    assert captured["url"].rstrip("/").endswith("/scrape")
    assert captured["headers"]["Authorization"] == "Bearer fc-test123"
    body = captured["json"]
    assert body["url"] == "https://x.com/a"
    assert "html" in body["formats"]
