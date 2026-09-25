"""TDD tests: Deep Dive Reddit/Amazon search + Refinement reuse."""
import asyncio
import pytest


@pytest.mark.asyncio
async def test_deep_dive_searches_reddit_and_amazon(monkeypatch):
    """Deep Dive must do 4 searches: specs, proscons, reddit, amazon."""
    from core.post_processors import product_deep_dive as pdd

    searches = []

    async def fake_search(product_name, kind):
        searches.append(kind)
        if kind == "reddit":
            return [{"url": "https://reddit.com/r/test",
                     "title": "User review",
                     "snippet": "As one user said: 'battery life is insane'"}]
        if kind == "amazon":
            return [{"url": "https://amazon.com/dp/test",
                     "title": "Amazon review",
                     "snippet": "Amazon customer: 'Worth every penny'"}]
        return [{"url": "https://rev.com", "title": "T", "snippet": "s"}]

    async def fake_main_text(url):
        return "Some page content"

    class FakeRouter:
        def __init__(self, *a, **k): pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            return ('{"key_specs": ["s"], "real_pros": ["p"], "real_cons": ["c"], '
                    '"user_quotes": [{"quote": "battery life is insane", '
                    '"source": "reddit.com"}], '
                    '"expert_verdict": "good", "best_for": "all", '
                    '"price_range": "$999", "target_audience": "everyone"}')

    monkeypatch.setattr(pdd, "_search_product", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    out = await pdd.deep_dive_product("MacBook Air M4")

    assert "reddit" in searches, f"Missing reddit search. Searches: {searches}"
    assert "amazon" in searches, f"Missing amazon search. Searches: {searches}"
    assert len(searches) == 4
    assert out["user_quotes"], "user_quotes should not be empty with reddit search"


@pytest.mark.asyncio
async def test_deep_dive_captures_verbatim_quotes(monkeypatch):
    """User quotes must be extracted verbatim from Reddit snippets."""
    from core.post_processors import product_deep_dive as pdd

    async def fake_search(product_name, kind):
        if kind == "reddit":
            return [{"url": "https://reddit.com/r/macbook",
                     "snippet": "User said: 'This thing is a beast, battery lasts forever'"}]
        return []

    async def fake_main_text(url):
        return None

    class FakeRouter:
        def __init__(self, *a, **k): pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            return ('{"key_specs": [], "real_pros": [], "real_cons": [], '
                    '"user_quotes": [{"quote": "This thing is a beast, '
                    'battery lasts forever", "source": "reddit.com"}], '
                    '"expert_verdict": "", "best_for": "", '
                    '"price_range": "", "target_audience": ""}')

    monkeypatch.setattr(pdd, "_search_product", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    out = await pdd.deep_dive_product("MacBook Air M4")
    assert len(out["user_quotes"]) >= 1
    assert "beast" in out["user_quotes"][0]["quote"]


def test_convert_deep_to_signals():
    """Helper must convert deep_dive data to signals format."""
    from core.post_processors.product_refiner import convert_deep_to_signals

    deep = {
        "found": True,
        "key_specs": ["M4 chip", "15.3-inch display"],
        "real_pros": ["long battery", "fast"],
        "real_cons": ["expensive"],
        "user_quotes": [
            {"quote": "battery lasts forever", "source": "reddit.com"},
            {"quote": "Worth every penny", "source": "amazon.com"},
        ],
        "price_range": "$1,299-$1,699",
        "target_audience": "creatives",
    }
    signals = convert_deep_to_signals(deep)
    assert signals["found"] is True
    assert "battery lasts forever" in signals["snippets"][0]
    assert "reddit.com" in signals["snippets"][0]
    assert len(signals["snippets"]) >= 2
    assert "long battery" in signals["praise"]
    assert "expensive" in signals["complaints"]


def test_convert_deep_to_signals_not_found():
    """When deep dive failed, return found=False."""
    from core.post_processors.product_refiner import convert_deep_to_signals
    signals = convert_deep_to_signals({"found": False})
    assert signals["found"] is False
    assert signals["snippets"] == []


@pytest.mark.asyncio
async def test_refinement_reuses_deep_data_no_search(monkeypatch):
    """When deep_data exists, gather_product_signals must NOT call Tavily."""
    from core.post_processors import product_refiner as pr

    search_calls = []

    async def fake_gather_signals(product_name, topic=""):
        search_calls.append(product_name)
        return {"found": True, "snippets": ["new snippet"]}

    monkeypatch.setattr(pr, "gather_product_signals", fake_gather_signals)

    deep_data = {
        "MacBook Air M4": {
            "found": True,
            "key_specs": ["M4"],
            "real_pros": ["fast"],
            "real_cons": ["expensive"],
            "user_quotes": [{"quote": "amazing", "source": "reddit.com"}],
            "price_range": "$1,299",
            "target_audience": "all",
        }
    }

    # Call with deep_data -> should NOT trigger new search
    signals = await pr.get_signals_for_product("MacBook Air M4", "laptops", deep_data)

    assert search_calls == [], f"Should not call gather_product_signals: {search_calls}"
    assert signals["found"] is True
    assert "amazing" in signals["snippets"][0]


@pytest.mark.asyncio
async def test_refinement_falls_back_when_deep_failed(monkeypatch):
    """When deep_data is missing/failed, fall back to normal search."""
    from core.post_processors import product_refiner as pr

    search_calls = []

    async def fake_gather_signals(product_name, topic=""):
        search_calls.append(product_name)
        return {"found": True, "snippets": ["fallback snippet"]}

    monkeypatch.setattr(pr, "gather_product_signals", fake_gather_signals)

    # No deep_data for this product
    signals = await pr.get_signals_for_product("Unknown Widget", "topic", {})

    assert search_calls == ["Unknown Widget"]  # Fallback triggered
    assert signals["found"] is True
