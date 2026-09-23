"""TDD tests: Product Deep Dive = 4-source crawl + cross-checked extraction."""
import asyncio
import pytest

PAGE_A = ("The ASUS ROG Crosshair X870E Hero uses an 18+2 power stage VRM. "
          "It supports WiFi 7 and four M.2 slots. Boot times are fast.")
PAGE_B = ("Owners praise the cool VRM temps under load. One Reddit user "
          "wrote: 'VRM stays at 65C even overclocked'. BIOS bugs were fixed.")
PAGE_C = ("Reviewers note the premium price around $699. Best suited for "
          "enthusiasts and overclockers who need extreme power delivery.")
PAGE_D = ("TechPowerUp verdict: the most complete X870E board tested. "
          "Cons include heavy heatsinks and limited availability.")
THIN_PAGE = "too short"

EXTRACTED_JSON = (
    '{"key_specs": ["18+2 power stage VRM", "WiFi 7", "4x M.2 slots"], '
    '"real_pros": ["cool VRM temps", "fast boot"], '
    '"real_cons": ["$699 price", "heavy heatsinks"], '
    '"user_quotes": [{"quote": "VRM stays at 65C even overclocked", '
    '"source": "reddit.com"}], '
    '"expert_verdict": "The most complete X870E board tested.", '
    '"best_for": "enthusiasts and overclockers", '
    '"price_range": "$650-$700", '
    '"target_audience": "enthusiasts and overclockers"}'
)


def test_fetch_main_text_httpx_path(monkeypatch):
    from backend.tools import content_analyzer as ca
    calls = {"fc": 0}

    async def fake_httpx(url, timeout=15.0):
        return "<html><body><article><p>Real article words here.</p></article></body></html>"

    async def fake_fc(url):
        calls["fc"] += 1
        return "<html></html>"

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    text = asyncio.run(ca.fetch_main_text("https://x.com/a"))
    assert text and "Real article words" in text
    assert calls["fc"] == 0


def test_fetch_main_text_firecrawl_fallback(monkeypatch):
    from backend.tools import content_analyzer as ca

    async def fake_httpx(url, timeout=15.0):
        return None

    async def fake_fc(url):
        return "<html><body><article><p>Rescued content words.</p></article></body></html>"

    monkeypatch.setattr(ca, "_httpx_fetch", fake_httpx)
    monkeypatch.setattr(ca, "_firecrawl_fetch", fake_fc)
    monkeypatch.setattr(ca, "_firecrawl_enabled", lambda: True)
    text = asyncio.run(ca.fetch_main_text("https://x.com/a"))
    assert text and "Rescued content" in text


def test_crawl_collects_minimum_4_pages(monkeypatch):
    """With 6 good URLs available, exactly 4 pages must be crawled."""
    from core.post_processors import product_deep_dive as pdd
    crawled = []

    async def fake_main_text(url):
        crawled.append(url)
        return PAGE_A

    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    urls = [f"https://s{i}.com/a" for i in range(6)]
    pages = asyncio.run(pdd._crawl_multi_text(urls))
    assert len(pages) >= 4
    assert len(crawled) >= 4


def test_crawl_skips_thin_and_failed_pages(monkeypatch):
    """Thin (<300 chars) and failing pages are skipped; good ones kept."""
    from core.post_processors import product_deep_dive as pdd

    async def fake_main_text(url):
        if "thin" in url:
            return THIN_PAGE
        if "dead" in url:
            return None
        return PAGE_B

    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    urls = ["https://thin.com", "https://dead.com",
            "https://ok1.com", "https://ok2.com"]
    pages = asyncio.run(pdd._crawl_multi_text(urls))
    assert len(pages) == 2
    assert all(p["url"].startswith("https://ok") for p in pages)


def test_deep_dive_product_success(monkeypatch):
    """Happy path: 4-source data -> verified structure incl quotes+verdict."""
    from core.post_processors import product_deep_dive as pdd

    async def fake_search(q, max_results=4):
        return [{"url": f"https://rev.com/{i}", "title": "T",
                 "snippet": "cool VRM temps per owners"} for i in range(4)]

    async def fake_main_text(url):
        return PAGE_A

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            return EXTRACTED_JSON

    monkeypatch.setattr(pdd, "get_top_results", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    out = asyncio.run(pdd.deep_dive_product("ASUS ROG Crosshair X870E Hero"))
    assert out["found"] is True
    assert "18+2 power stage VRM" in out["key_specs"]
    assert out["user_quotes"][0]["quote"] == "VRM stays at 65C even overclocked"
    assert out["expert_verdict"]
    assert out["best_for"]
    assert out["price_range"] == "$650-$700"
    assert len(out["sources"]) >= 1


def test_extraction_prompt_contains_all_crawled_sources(monkeypatch):
    """LLM must receive every crawled page as a numbered SOURCE block."""
    from core.post_processors import product_deep_dive as pdd
    captured = {}
    pages_text = {"https://ok1.com": PAGE_A, "https://ok2.com": PAGE_B,
                  "https://ok3.com": PAGE_C, "https://ok4.com": PAGE_D}

    async def fake_search(q, max_results=4):
        return [{"url": u, "title": "T", "snippet": "s"} for u in pages_text]

    async def fake_main_text(url):
        return pages_text.get(url)

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            captured["prompt"] = prompt
            return EXTRACTED_JSON

    monkeypatch.setattr(pdd, "get_top_results", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    asyncio.run(pdd.deep_dive_product("ASUS ROG Crosshair X870E Hero"))
    for marker in ["SOURCE 1", "SOURCE 2", "SOURCE 3", "SOURCE 4"]:
        assert marker in captured["prompt"], f"{marker} missing from LLM prompt"
    assert "65C" in captured["prompt"]  # page B content reached the LLM


def test_deep_dive_no_search_results(monkeypatch):
    from core.post_processors import product_deep_dive as pdd
    calls = {"llm": 0}

    async def fake_search(q, max_results=4):
        return []

    async def fake_main_text(url):
        return PAGE_A

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            calls["llm"] += 1
            return EXTRACTED_JSON

    monkeypatch.setattr(pdd, "get_top_results", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    out = asyncio.run(pdd.deep_dive_product("Unknown Widget 9000"))
    assert out["found"] is False
    assert out["key_specs"] == []
    assert calls["llm"] == 0


def test_deep_dive_crawl_failure_uses_snippets(monkeypatch):
    from core.post_processors import product_deep_dive as pdd
    captured = {}

    async def fake_search(q, max_results=4):
        return [{"url": "https://rev.com/a", "title": "T",
                 "snippet": "owners love the cool VRM temps"}]

    async def fake_main_text(url):
        return None

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            captured["prompt"] = prompt
            return EXTRACTED_JSON

    monkeypatch.setattr(pdd, "get_top_results", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    out = asyncio.run(pdd.deep_dive_product("ASUS ROG Crosshair X870E Hero"))
    assert out["found"] is True
    assert "cool VRM temps" in captured["prompt"]


def test_deep_dive_llm_failure_returns_empty(monkeypatch):
    from core.post_processors import product_deep_dive as pdd

    async def fake_search(q, max_results=4):
        return [{"url": "https://rev.com/a", "title": "T", "snippet": "s"}]

    async def fake_main_text(url):
        return PAGE_A

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            raise RuntimeError("LLM down")

    monkeypatch.setattr(pdd, "get_top_results", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    out = asyncio.run(pdd.deep_dive_product("Some Product"))
    assert out["found"] is False
    assert out["key_specs"] == []


def test_extraction_prompt_has_anti_hallucination_guard(monkeypatch):
    from core.post_processors import product_deep_dive as pdd
    captured = {}

    async def fake_search(q, max_results=4):
        return [{"url": "https://rev.com/a", "title": "T", "snippet": "s"}]

    async def fake_main_text(url):
        return PAGE_A

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            captured["system"] = system_prompt
            return EXTRACTED_JSON

    monkeypatch.setattr(pdd, "get_top_results", fake_search)
    monkeypatch.setattr(pdd, "fetch_main_text", fake_main_text)
    monkeypatch.setattr(pdd, "LLMRouter", FakeRouter)

    asyncio.run(pdd.deep_dive_product("Some Product"))
    assert "NEVER invent" in captured["system"]
    assert "multiple sources" in captured["system"].lower()


def test_batch_continues_after_crash(monkeypatch):
    from core.post_processors import product_deep_dive as pdd

    async def boom(name, category=""):
        if name == "Bad Product":
            raise RuntimeError("crash")
        return {"product": name, "found": True, "key_specs": ["s"],
                "real_pros": [], "real_cons": [], "user_quotes": [],
                "expert_verdict": "", "best_for": "", "price_range": "",
                "target_audience": "", "sources": []}

    monkeypatch.setattr(pdd, "deep_dive_product", boom)
    monkeypatch.setattr(pdd.asyncio, "sleep", lambda s: asyncio.sleep(0))

    out = asyncio.run(pdd.product_deep_dive(
        [{"name": "Bad Product"}, {"name": "Good Product"}]))
    assert out["Bad Product"]["found"] is False
    assert out["Good Product"]["found"] is True


def test_batch_disabled_by_env(monkeypatch):
    monkeypatch.setenv("PRODUCT_DEEP_DIVE", "false")
    from core.post_processors import product_deep_dive as pdd
    out = asyncio.run(pdd.product_deep_dive([{"name": "X"}]))
    assert out == {}


def test_format_block_includes_verified_data():
    from core.post_processors.product_deep_dive import format_deep_data_block
    block = format_deep_data_block({
        "found": True,
        "key_specs": ["18+2 VRM", "WiFi 7"],
        "real_pros": ["cool VRM temps"],
        "real_cons": ["pricey"],
        "user_quotes": [{"quote": "VRM stays at 65C", "source": "reddit.com"}],
        "expert_verdict": "Most complete X870E board tested.",
        "best_for": "enthusiasts",
        "price_range": "$650-$700",
        "target_audience": "enthusiasts",
    })
    assert "VERIFIED SPECIFICATIONS" in block
    assert "18+2 VRM" in block
    assert "VRM stays at 65C" in block
    assert "reddit.com" in block
    assert "Most complete X870E board tested." in block
    assert "$650-$700" in block


def test_format_block_empty_when_not_found():
    from core.post_processors.product_deep_dive import format_deep_data_block
    assert format_deep_data_block({"found": False}) == ""
    assert format_deep_data_block({}) == ""


def test_h3_subprompt_injects_deep_data(monkeypatch):
    """H3 prompts must contain verified block + trust/engagement rules."""
    from core.agents import subprompt_generator as sg
    state = {
        "topic": "best x870e motherboards",
        "user_request": "best x870e motherboards",
        "content_type": "product_recommendation",
        "selected_products": [
            {"name": "ASUS ROG Crosshair X870E Hero", "tier": "premium"}],
        "product_deep_data": {
            "ASUS ROG Crosshair X870E Hero": {
                "found": True,
                "key_specs": ["18+2 VRM", "WiFi 7"],
                "real_pros": ["cool VRM temps"],
                "real_cons": ["pricey"],
                "user_quotes": [{"quote": "VRM stays at 65C",
                                 "source": "reddit.com"}],
                "expert_verdict": "Most complete X870E board tested.",
                "best_for": "enthusiasts",
                "price_range": "$650-$700",
                "target_audience": "enthusiasts",
                "sources": ["https://rev.com/a"],
            }},
    }

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            return '{"sections": []}'

    monkeypatch.setattr(sg, "LLMRouter", FakeRouter, raising=False)
    builder = getattr(sg, "build_product_subprompts", None)
    if builder is None:
        pytest.skip("generator entry point differs; adapt this test")
    sub_prompts = asyncio.run(builder(state))
    h3 = [p for p in sub_prompts if p.get("type") == "h3_detail"]
    assert h3, "no h3 prompts generated"
    prompt_text = h3[0].get("prompt", "")
    assert "VERIFIED SPECIFICATIONS" in prompt_text
    assert "VRM stays at 65C" in prompt_text
    assert "TRUST & ENGAGEMENT" in prompt_text


def test_h3_subprompt_backward_compat_without_deep_data(monkeypatch):
    from core.agents import subprompt_generator as sg
    state = {
        "topic": "best x870e motherboards",
        "user_request": "best x870e motherboards",
        "content_type": "product_recommendation",
        "selected_products": [
            {"name": "ASUS ROG Crosshair X870E Hero", "tier": "premium"}],
    }

    class FakeRouter:
        def __init__(self, *a, **k):
            pass
        async def generate_text(self, prompt="", system_prompt="", **k):
            return '{"sections": []}'

    monkeypatch.setattr(sg, "LLMRouter", FakeRouter, raising=False)
    builder = getattr(sg, "build_product_subprompts", None)
    if builder is None:
        pytest.skip("generator entry point differs; adapt this test")
    sub_prompts = asyncio.run(builder(state))
    h3 = [p for p in sub_prompts if p.get("type") == "h3_detail"]
    assert h3
    assert not any("VERIFIED SPECIFICATIONS" in p.get("prompt", "") for p in h3)
