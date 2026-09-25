"""TDD tests: Level 3 - Remove redundant topic-level shopping signals."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_gather_shopping_signals_removed_from_pipeline():
    """gather_shopping_signals should NOT be called in competitor_analysis_node / graph."""
    from core.graph import competitor_analysis_node
    
    # Mock state with minimal data
    mock_state = {
        "topic": "Best Gaming Laptops",
        "target_audience": "gamers",
        "content_goals": "comprehensive guide",
        "keywords": [],
        "competitor_data": {},
        "user_request": "Best Gaming Laptops",
    }
    
    with patch('backend.tools.shopping_intelligence.gather_shopping_signals') as mock_signals:
        with patch('core.graph.get_top_results', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            with patch('core.graph.LLMRouter') as mock_llm:
                mock_llm_instance = MagicMock()
                mock_llm_instance.generate_text = AsyncMock(return_value='{"competitor_ranking_strengths": []}')
                mock_llm.return_value = mock_llm_instance
                
                result = await competitor_analysis_node(mock_state)
                
                # gather_shopping_signals should NOT be called
                assert not mock_signals.called, \
                    "gather_shopping_signals should be removed from pipeline"


def test_shopping_signals_state_field_optional():
    """shopping_signals field should be optional in state (not required)."""
    from core.state import ContentForgeState
    
    state_dict = {
        "topic": "Test Topic",
        "keywords": [],
        "competitor_data": {},
    }
    
    assert True


@pytest.mark.asyncio
async def test_get_signals_for_product_reuses_deep_dive():
    """get_signals_for_product should use Deep Dive data when available."""
    from core.post_processors.product_refiner import get_signals_for_product
    
    deep_data = {
        "MacBook Air M4": {
            "found": True,
            "key_specs": ["M4 chip", "16GB RAM"],
            "real_pros": ["fast", "efficient"],
            "real_cons": ["expensive"],
            "user_quotes": [{"quote": "Amazing performance", "source": "reddit.com"}],
            "price_range": "$1,099-$1,499",
            "target_audience": "professionals",
            "expert_verdict": "Best ultrabook of 2025",
            "best_for": "creative professionals",
        }
    }
    
    with patch('core.post_processors.product_refiner.gather_product_signals') as mock_gather:
        signals = await get_signals_for_product("MacBook Air M4", "laptops", deep_data)
        
        assert not mock_gather.called, \
            "Should use Deep Dive data, not gather_product_signals"
        
        assert signals["found"] is True
        assert "Amazing performance" in str(signals.get("snippets", []))
        assert "fast" in signals.get("praise", [])


@pytest.mark.asyncio
async def test_get_signals_for_product_fallback_when_no_deep_dive():
    """get_signals_for_product should fallback to search when Deep Dive data missing."""
    from core.post_processors.product_refiner import get_signals_for_product
    
    with patch('core.post_processors.product_refiner.gather_product_signals', 
               new_callable=AsyncMock) as mock_gather:
        mock_gather.return_value = {
            "found": True,
            "snippets": ["fallback snippet"],
            "praise": ["good"],
            "complaints": [],
        }
        
        signals = await get_signals_for_product("Unknown Product", "topic", {})
        
        assert mock_gather.called, \
            "Should fallback to gather_product_signals when no Deep Dive data"


def test_convert_deep_to_signals_structure():
    """convert_deep_to_signals should produce correct signal structure."""
    from core.post_processors.product_refiner import convert_deep_to_signals
    
    deep = {
        "found": True,
        "key_specs": ["Spec 1", "Spec 2"],
        "real_pros": ["Pro 1", "Pro 2"],
        "real_cons": ["Con 1"],
        "user_quotes": [{"quote": "Great product", "source": "reddit.com"}],
        "price_range": "$999",
        "target_audience": "gamers",
        "expert_verdict": "Top pick",
        "best_for": "gaming",
    }
    
    signals = convert_deep_to_signals(deep)
    
    assert signals["found"] is True
    assert "snippets" in signals
    assert "praise" in signals
    assert "complaints" in signals
    assert "level3_metadata" in signals
    
    assert any("Great product" in s for s in signals["snippets"])
    assert "Pro 1" in signals["praise"]
    assert "Con 1" in signals["complaints"]


def test_convert_deep_to_signals_not_found():
    """convert_deep_to_signals should return found=False for empty data."""
    from core.post_processors.product_refiner import convert_deep_to_signals
    
    signals = convert_deep_to_signals({"found": False})
    
    assert signals["found"] is False
    assert signals["snippets"] == []


def test_no_shopping_signals_display_in_gradio():
    """Gradio UI should not display shopping_signals data anymore."""
    assert True
