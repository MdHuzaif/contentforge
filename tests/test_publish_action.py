"""Test publish_to_uniscolian_action independently (no UI launch required)."""
from __future__ import annotations
import sys, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from unittest.mock import AsyncMock, patch, MagicMock
import app.gradio_app as ga


class FakeSnap(dict):
    """Minimal stand-in for LangGraph state snapshot."""
    def __init__(self, values):
        super().__init__({"values": values})
    def get(self, k, default=None):
        return dict.get(self, k, default)


@pytest.fixture
def mock_session():
    """Mock InteractiveSession with minimal blog state."""
    session = MagicMock()
    session.get_state = AsyncMock(return_value=FakeSnap({
        "assembled_blog": "# Test Blog\n## Intro\nSome content here.",
        "topic": "best budget laptops 2026",
        "keyword_research": {"keywords": [{"keyword": "laptop"}, {"keyword": "budget"}]},
        "product_affiliate_links": {},
        "product_images_map": {},
        "detected_products": [],
    }))
    return session


@pytest.mark.asyncio
async def test_publish_action_without_update_url(mock_session):
    """Empty update_url should trigger normal new-post flow."""
    with patch("app.gradio_app.get_session", new_callable=AsyncMock, return_value=mock_session):
        with patch("app.gradio_app.export_post_to_uniscolian", return_value={
            "slug": "best-budget-laptops-2026",
            "path": "/tmp/test/index.html",
            "read_time": 1,
            "expected_images": [],
            "image": {},
            "sitemap_updated": True,
            "slug_renamed": False,
            "related": [],
            "word_count": 5,
            "updated": False,
        }):
            result = await ga.publish_to_uniscolian_action("test-thread-id", "")
    
    assert "Successfully Published" in result
    assert "best-budget-laptops-2026" in result


@pytest.mark.asyncio
async def test_publish_action_with_valid_update_url(mock_session):
    """Valid slug should trigger update mode."""
    with patch("app.gradio_app.get_session", new_callable=AsyncMock, return_value=mock_session):
        with patch("app.gradio_app.export_post_to_uniscolian", return_value={
            "slug": "existing-post",
            "path": "/tmp/existing/index.html",
            "read_time": 2,
            "expected_images": [],
            "image": {},
            "sitemap_updated": False,
            "slug_renamed": False,
            "related": [],
            "word_count": 10,
            "updated": True,
        }):
            result = await ga.publish_to_uniscolian_action(
                "test-thread-id", 
                "https://uniscolian.com/existing-post/"
            )
    
    assert "Post UPDATED" in result
    assert "existing-post" in result


@pytest.mark.asyncio
async def test_publish_action_with_invalid_url(mock_session):
    """Invalid URL (path traversal) should return error, not crash."""
    with patch("app.gradio_app.get_session", new_callable=AsyncMock, return_value=mock_session):
        result = await ga.publish_to_uniscolian_action(
            "test-thread-id",
            "../../etc/passwd"
        )
    
    assert "❌" in result
    assert "Invalid" in result or "traversal" in result


@pytest.mark.asyncio
async def test_publish_action_with_nonexistent_slug(mock_session):
    """Non-existent slug should return error from exporter."""
    with patch("app.gradio_app.get_session", new_callable=AsyncMock, return_value=mock_session):
        with patch("app.gradio_app.export_post_to_uniscolian", return_value={
            "error": "Post not found: /ghost-post/ — nothing was changed.",
            "updated": False,
            "slug": "ghost-post",
            "slug_renamed": False,
            "sitemap_updated": False,
            "path": "",
            "url": "/ghost-post/",
            "word_count": 0,
            "read_time": 0,
            "expected_images": [],
            "image": {},
            "related": [],
        }):
            result = await ga.publish_to_uniscolian_action("test-thread-id", "ghost-post")
    
    assert "❌" in result
    assert "Post not found" in result


@pytest.mark.asyncio
async def test_publish_action_with_empty_thread_id():
    """No thread_id should return session error."""
    result = await ga.publish_to_uniscolian_action("", "some-slug")
    assert "❌" in result
    assert "active session" in result


@pytest.mark.asyncio  
async def test_parse_update_target_is_importable():
    """Regression: parse_update_target must be importable at module level."""
    # This catches the NameError that just happened
    from app.gradio_app import parse_update_target
    assert callable(parse_update_target)
    assert parse_update_target("https://uniscolian.com/my-post/") == "my-post"


@pytest.mark.asyncio
async def test_export_post_called_with_update_slug(mock_session):
    """Verify update_slug parameter is actually passed to exporter."""
    captured_kwargs = {}
    
    def capture_call(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "slug": "my-post", "path": "/x/index.html", "read_time": 1,
            "expected_images": [], "image": {}, "sitemap_updated": False,
            "slug_renamed": False, "related": [], "word_count": 5, "updated": True,
        }
    
    with patch("app.gradio_app.get_session", new_callable=AsyncMock, return_value=mock_session):
        with patch("app.gradio_app.export_post_to_uniscolian", side_effect=capture_call):
            await ga.publish_to_uniscolian_action("tid", "https://uniscolian.com/my-post/")
    
    assert captured_kwargs.get("update_slug") == "my-post"
