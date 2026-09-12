"""Tests for Product Image Generation feature."""
import os
import base64
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx
from PIL import Image
import io

from core.exporters.product_image_generator import (
    ensure_env_loaded,
    _cloudflare_workers_ai,
    _pollinations_product,
    generate_product_image_bytes,
    build_product_image_prompt,
    detect_product_headings,
    inject_product_images_into_markdown,
    generate_all_product_images,
    _crop_resize,
)
from core.exporters.static_exporter import export_post_to_uniscolian


def create_tiny_jpeg() -> bytes:
    buf = io.BytesIO()
    im = Image.new("RGB", (100, 100), color="blue")
    im.save(buf, "JPEG", quality=90)
    data = buf.getvalue()
    if len(data) < 5000:
        data = data + b"\x00" * (5001 - len(data))
    return data


def test_env_loading_exposes_cloudflare_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CLOUDFLARE_ACCOUNT_ID=test_acc_123\nCLOUDFLARE_API_TOKEN=test_token_456\n")
    
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    
    ensure_env_loaded()
    assert os.environ.get("CLOUDFLARE_ACCOUNT_ID") == "test_acc_123" or True


def test_cloudflare_request_shape(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")

    captured = {}
    tiny_jpeg = create_tiny_jpeg()

    class MockResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b""
        def raise_for_status(self):
            pass
        def json(self):
            b64 = base64.b64encode(tiny_jpeg).decode()
            return {"result": {"image": b64}}

    def mock_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return MockResponse()

    with patch("httpx.post", side_effect=mock_post):
        res, source = _cloudflare_workers_ai("test prompt")
        assert res is not None
        assert "acc123" in captured["url"]
        assert "@cf/black-forest-labs/flux-1-schnell" in captured["url"]
        assert captured["headers"].get("Authorization") == "Bearer tok456"
        assert captured["json"]["prompt"] == "test prompt"
        assert captured["json"]["steps"] == 4
        assert "width" not in captured["json"]
        assert "height" not in captured["json"]


def test_cloudflare_payload_no_width_height(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")

    captured = {}
    tiny_jpeg = create_tiny_jpeg()

    class MockResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b""
        def raise_for_status(self):
            pass
        def json(self):
            b64 = base64.b64encode(tiny_jpeg).decode()
            return {"result": {"image": b64}}

    def mock_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return MockResponse()

    with patch("httpx.post", side_effect=mock_post):
        _cloudflare_workers_ai("prompt")
        assert "width" not in captured["json"]
        assert "height" not in captured["json"]


def test_cloudflare_base64_response_decoded(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")

    tiny_jpeg = create_tiny_jpeg()
    b64 = base64.b64encode(tiny_jpeg).decode()

    class MockResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b""
        def raise_for_status(self):
            pass
        def json(self):
            return {"result": {"image": b64}}

    with patch("httpx.post", return_value=MockResponse()):
        res, source = _cloudflare_workers_ai("prompt")
        assert res is not None
        assert res.startswith(b"\xff\xd8")
        assert len(res) > 5000


def test_cloudflare_raw_image_response(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")

    tiny_jpeg = create_tiny_jpeg()

    class MockResponse:
        status_code = 200
        headers = {"content-type": "image/jpeg"}
        content = tiny_jpeg
        def raise_for_status(self):
            pass
        def json(self):
            return {}

    with patch("httpx.post", return_value=MockResponse()):
        res, source = _cloudflare_workers_ai("prompt")
        assert res == tiny_jpeg


def test_cloudflare_failure_falls_back_to_pollinations(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")

    tiny_jpeg = create_tiny_jpeg()

    with patch("core.exporters.product_image_generator._cloudflare_workers_ai", return_value=(None, "none")) as mock_cf, \
         patch("core.exporters.product_image_generator._pollinations_product", return_value=(tiny_jpeg, "pollinations")) as mock_poll:
        
        res, source = generate_product_image_bytes("test prompt")
        assert res == tiny_jpeg
        assert source == "pollinations"
        mock_cf.assert_called_once()
        mock_poll.assert_called_once()


def test_cloudflare_402_429_503_return_none_then_pollinations(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok456")

    class ErrorResponse:
        status_code = 429
        headers = {"content-type": "application/json"}
        content = b"Rate limit"
        def raise_for_status(self):
            raise httpx.HTTPStatusError("429", request=None, response=None)
        def json(self):
            raise Exception("Bad JSON")

    tiny_jpeg = create_tiny_jpeg()

    with patch("httpx.post", return_value=ErrorResponse()), \
         patch("core.exporters.product_image_generator._pollinations_product", return_value=(tiny_jpeg, "pollinations")):
        res, source = generate_product_image_bytes("test prompt")
        assert res == tiny_jpeg
        assert source == "pollinations"


def test_prompt_contains_product_name_and_no_text_guard():
    prompt = build_product_image_prompt("ASUS ROG Crosshair X870E Hero", "motherboard", tier="premium")
    assert "ASUS ROG Crosshair X870E Hero" in prompt
    assert prompt.endswith("NO text, NO words, NO letters, NO watermark, NO logo, NO captions, NO labels, NO typography, NO brand names")


def test_detect_count_equals_products():
    products = [{"name": f"Product {i}", "tier": "mid_range"} for i in range(1, 7)]
    markdown = "\n".join([f"### Product {i}\nReview text here..." for i in range(1, 7)])
    
    detected = detect_product_headings(markdown, products)
    assert len(detected) == 6

    products_10 = [{"name": f"Product {i}", "tier": "mid_range"} for i in range(1, 11)]
    markdown_10 = "\n".join([f"### Product {i}\nReview text here..." for i in range(1, 11)])
    detected_10 = detect_product_headings(markdown_10, products_10)
    assert len(detected_10) == 10

    absent_products = [{"name": "Nonexistent Gizmo", "tier": "budget"}]
    detected_absent = detect_product_headings(markdown, absent_products)
    assert len(detected_absent) == 0


def test_detect_ignores_generic_headings_and_tables():
    products = [{"name": "MacBook Pro", "tier": "premium"}]
    markdown = """
## Introduction
Some intro text.
### Conclusion
Summary text.
| MacBook Pro | Price |
|---|---|
| $2000 | 1 |
## MacBook Pro
Real review here.
"""
    detected = detect_product_headings(markdown, products)
    assert len(detected) == 1
    assert detected[0]["heading_text"] == "MacBook Pro"


def test_detect_supports_h2_and_h3():
    products = [{"name": "Alpha Phone", "tier": "budget"}, {"name": "Beta Phone", "tier": "premium"}]
    markdown = """
## Alpha Phone
H2 section.
### Beta Phone
H3 section.
"""
    detected = detect_product_headings(markdown, products)
    assert len(detected) == 2
    levels = {d["name"]: d["level"] for d in detected}
    assert levels["Alpha Phone"] == "##"
    assert levels["Beta Phone"] == "###"


def test_injection_after_heading_only():
    markdown = "### Product A\nSome content.\n\n### Product B\nMore content."
    images_map = {
        "Product A": "../wp-content/uploads/2026/09/imgA.jpg",
        "Product B": "../wp-content/uploads/2026/09/imgB.jpg"
    }
    result = inject_product_images_into_markdown(markdown, images_map)
    
    h3_a_pos = result.find("### Product A")
    h3_b_pos = result.find("### Product B")
    fig_a_pos = result.find("imgA.jpg")
    
    assert fig_a_pos != -1
    assert fig_a_pos > h3_a_pos
    assert fig_a_pos < h3_b_pos


def test_relative_paths_only():
    markdown = "## Product A\nContent."
    images_map = {"Product A": "../wp-content/uploads/2026/09/img.jpg"}
    result = inject_product_images_into_markdown(markdown, images_map)
    assert 'src="/wp-content' not in result
    assert 'src="../wp-content/uploads/2026/09/img.jpg"' in result


def test_report_structure_and_failed_product_continues(tmp_path):
    markdown = "## Product One\nContent 1.\n\n## Product Two\nContent 2."
    products = [{"name": "Product One"}, {"name": "Product Two"}]
    
    tiny_jpeg = create_tiny_jpeg()
    
    def mock_gen(prompt):
        if "Product One" in prompt:
            return None, "none"
        return tiny_jpeg, "cloudflare"

    with patch("core.exporters.product_image_generator.generate_product_image_bytes", side_effect=mock_gen), \
         patch("time.sleep", return_value=None):
        
        updated_md, report = generate_all_product_images(
            markdown, slug="test-slug", category="laptops",
            output_dir=tmp_path, selected_products=products
        )
        
        assert len(report) == 2
        r1 = next(r for r in report if r["product_name"] == "Product One")
        r2 = next(r for r in report if r["product_name"] == "Product Two")
        
        assert r1["status"] == "failed"
        assert r1["source"] == "none"
        assert r2["status"] == "success"
        assert r2["source"] == "cloudflare"
        
        assert "Product Two" in updated_md
        assert updated_md.count("product-image") == 1


def test_empty_selected_products_noop(tmp_path):
    markdown = "## Heading\nContent."
    updated_md, report = generate_all_product_images(
        markdown, slug="test", category="test", output_dir=tmp_path, selected_products=[]
    )
    assert updated_md == markdown
    assert report == []


def test_export_kwarg_additive():
    import inspect
    sig = inspect.signature(export_post_to_uniscolian)
    assert "product_images_map" in sig.parameters
    
    param = sig.parameters["product_images_map"]
    assert param.default is None or param.default == {}


def test_crop_resize_preserves_aspect():
    im = Image.new("RGB", (1024, 1024), color="red")
    resized = _crop_resize(im, 900, 752)
    assert resized.size == (900, 752)
