"""BS4-based analyzer: accuracy tests that regex parsing fails."""
import pytest

NAV_POLLUTED = """<html><head><title>T</title>
<meta name="description" content="Desc here.">
<script type="application/ld+json">{"@type":"FAQPage"}</script>
</head><body>
<nav><h2>Menu Heading</h2><ul><li>a</li><li>b</li></ul></nav>
<footer><h2>Footer Heading</h2><p>footer words footer words footer words</p></footer>
<article>
<h1>Main Title</h1>
<h2>Real Section One</h2>
<p>One two three four five six seven eight nine ten eleven twelve.</p>
<h2>Real Section Two</h2>
<table><tr><td>A</td><td>B</td></tr></table>
<ul><li>item one</li><li>item two</li></ul>
<iframe src="https://www.youtube.com/embed/xyz"></iframe>
</article>
<script>var junk = "hidden script words hidden script words";</script>
</body></html>"""

MALFORMED = "<html><body><h2>Unclosed Heading<p>text one two three four five"


def test_headings_ignore_nav_and_footer():
    from backend.tools.content_analyzer import extract_headings
    h = extract_headings(NAV_POLLUTED)
    assert "Menu Heading" not in h["h2"]
    assert "Footer Heading" not in h["h2"]
    assert h["h2"] == ["Real Section One", "Real Section Two"]
    assert h["h1"] == ["Main Title"]


def test_word_count_excludes_nav_script_footer():
    from backend.tools.content_analyzer import analyze_html
    info = analyze_html(NAV_POLLUTED)
    # article has ~24 words; nav/footer/script must NOT inflate it
    assert info["word_count"] < 40, f"word count inflated: {info['word_count']}"
    assert info["word_count"] >= 20


def test_malformed_html_still_parses():
    from backend.tools.content_analyzer import extract_headings
    h = extract_headings(MALFORMED)
    assert h["h2"] == ["Unclosed Heading"]


def test_meta_and_schema_detection():
    from backend.tools.content_analyzer import get_meta_info
    m = get_meta_info(NAV_POLLUTED)
    assert m["title"] == "T"
    assert m["meta_description"] == "Desc here."
    assert m["has_meta_description"] is True
    assert m["has_schema"] is True  # ld+json present


def test_engagement_signals_from_html():
    from backend.tools.content_analyzer import analyze_html
    info = analyze_html(NAV_POLLUTED)
    sig = info["engagement_signals"]
    assert sig["has_table"] is True
    assert sig["has_lists"] is True
    assert sig["has_video_embed"] is True
    assert sig["has_faq"] is True  # FAQPage schema


def test_main_text_prefers_article():
    from backend.tools.content_analyzer import extract_main_text
    text = extract_main_text(NAV_POLLUTED)
    assert "Real Section One" in text
    assert "Menu Heading" not in text
    assert "hidden script words" not in text


def test_output_keys_unchanged():
    """analyze_html dict keys must stay identical for callers."""
    from backend.tools.content_analyzer import analyze_html
    info = analyze_html(NAV_POLLUTED)
    for key in ["word_count", "h1_count", "h2_count", "h3_count",
                "headings", "image_count", "total_links",
                "external_links_count", "meta", "readability",
                "avg_sentence_length", "engagement_signals"]:
        assert key in info, f"missing key: {key}"
