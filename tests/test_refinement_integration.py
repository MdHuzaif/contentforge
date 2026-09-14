"""Integration test: Shopping signals must be injected into LLM prompts."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.post_processors.product_refiner import refine_blog_products

@pytest.mark.asyncio
async def test_shopping_signals_injected_into_llm_prompt():
    """Verify that praise/complaints/tier are passed to LLM during refinement."""
    
    # Mock blog with product sections (at least 2 products for refinement threshold)
    blog_md = """
# Best Laptops

## Top Picks

### 1. MacBook Air M2
The MacBook Air M2 is a powerful laptop for productivity.

### 2. ASUS VivoBook 15
The ASUS VivoBook 15 offers solid performance.
"""
    
    # Mock shopping signals (like what DuckDuckGo returns)
    mock_signals = {
        "found": True,
        "praise": ["fast", "powerful", "cool"],
        "complaints": ["expensive", "heavy"],
        "level3_metadata": {
            "tier": "premium",
            "popularity": 9,
            "brand": "Apple",
            "selling_points": ["M2 architecture"],
            "existing_pros": [],
            "existing_cons": []
        }
    }
    
    # Mock the signal gathering function
    with patch('core.post_processors.product_refiner.gather_product_signals', 
               new_callable=AsyncMock) as mock_gather:
        mock_gather.return_value = mock_signals
        
        # Mock LLM call to capture the prompt
        captured_prompts = []
        async def mock_llm_call(prompt: str) -> str:
            captured_prompts.append(prompt)
            return "Refined content with user feedback"
        
        with patch('core.post_processors.product_refiner.call_llm', 
                   new_callable=AsyncMock, side_effect=mock_llm_call):
            result = await refine_blog_products(blog_md, "best laptop")
    
    # CRITICAL ASSERTIONS
    assert len(captured_prompts) > 0, "LLM was never called"
    
    prompt = captured_prompts[0]
    
    # Verify signals are IN the prompt
    assert "fast" in prompt.lower() or "powerful" in prompt.lower(), \
        f"Praise signals not in LLM prompt. Prompt: {prompt[:500]}"
    assert "expensive" in prompt.lower() or "heavy" in prompt.lower(), \
        f"Complaint signals not in LLM prompt. Prompt: {prompt[:500]}"
    assert "premium" in prompt.lower(), \
        f"Tier not in LLM prompt. Prompt: {prompt[:500]}"
    
    print(f"[SUCCESS] Shopping signals found in LLM prompt")

@pytest.mark.asyncio
async def test_refinement_with_empty_signals_still_works():
    """Refinement should work even if no signals available."""
    blog_md = """
## Top Picks
### 1. MacBook Air M2
Content A.
### 2. ASUS VivoBook 15
Content B.
"""
    
    with patch('core.post_processors.product_refiner.gather_product_signals',
               new_callable=AsyncMock) as mock_gather:
        mock_gather.return_value = {"found": False, "praise": [], "complaints": []}
        
        with patch('core.post_processors.product_refiner.call_llm',
                   new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Refined content"
            result = await refine_blog_products(blog_md, "test")
    
    assert result is not None
    assert "refined_blog" in result

@pytest.mark.asyncio
async def test_level3_metadata_tier_used_in_prompt():
    """Verify tier information (premium/budget/mid_range) is used."""
    blog_md = """
## Top Picks
### 1. MacBook Air M2
Content A.
### 2. ASUS VivoBook 15
Content B.
"""
    
    mock_signals = {
        "found": True,
        "praise": ["cheap"],
        "complaints": [],
        "level3_metadata": {"tier": "budget", "popularity": 5}
    }
    
    captured_prompts = []
    async def mock_llm(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Refined"
    
    with patch('core.post_processors.product_refiner.gather_product_signals',
               new_callable=AsyncMock, return_value=mock_signals):
        with patch('core.post_processors.product_refiner.call_llm',
                   new_callable=AsyncMock, side_effect=mock_llm):
            await refine_blog_products(blog_md, "budget gpu")
    
    assert len(captured_prompts) > 0
    prompt = captured_prompts[0]
    assert "budget" in prompt.lower(), f"Tier 'budget' not in prompt: {prompt[:500]}"

@pytest.mark.asyncio
async def test_refinement_with_only_praise():
    """Works when only praise exists, no complaints."""
    blog_md = """
## Top Picks
### 1. MacBook Air M2
Content A.
### 2. ASUS VivoBook 15
Content B.
"""
    mock_signals = {
        "found": True,
        "praise": ["amazing"],
        "complaints": [],
        "level3_metadata": {"tier": "premium"}
    }
    captured_prompts = []
    async def mock_llm(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Refined praise"
    
    with patch('core.post_processors.product_refiner.gather_product_signals',
               new_callable=AsyncMock, return_value=mock_signals):
        with patch('core.post_processors.product_refiner.call_llm',
                   new_callable=AsyncMock, side_effect=mock_llm):
            await refine_blog_products(blog_md, "test")
    assert len(captured_prompts) > 0
    assert "amazing" in captured_prompts[0].lower()

@pytest.mark.asyncio  
async def test_refinement_with_only_complaints():
    """Works when only complaints exist."""
    blog_md = """
## Top Picks
### 1. MacBook Air M2
Content A.
### 2. ASUS VivoBook 15
Content B.
"""
    mock_signals = {
        "found": True,
        "praise": [],
        "complaints": ["flawed"],
        "level3_metadata": {"tier": "budget"}
    }
    captured_prompts = []
    async def mock_llm(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Refined complaints"
    
    with patch('core.post_processors.product_refiner.gather_product_signals',
               new_callable=AsyncMock, return_value=mock_signals):
        with patch('core.post_processors.product_refiner.call_llm',
                   new_callable=AsyncMock, side_effect=mock_llm):
            await refine_blog_products(blog_md, "test")
    assert len(captured_prompts) > 0
    assert "flawed" in captured_prompts[0].lower()

@pytest.mark.asyncio
async def test_refinement_preserves_original_on_llm_failure():
    """If LLM fails, original content is preserved."""
    blog_md = """
## Top Picks
### 1. MacBook Air M2
Original content A.
### 2. ASUS VivoBook 15
Original content B.
"""
    mock_signals = {
        "found": True,
        "praise": ["good"],
        "complaints": [],
    }
    with patch('core.post_processors.product_refiner.gather_product_signals',
               new_callable=AsyncMock, return_value=mock_signals):
        with patch('core.post_processors.product_refiner.call_llm',
                   new_callable=AsyncMock, side_effect=Exception("LLM Error")):
            result = await refine_blog_products(blog_md, "test")
    assert result is not None
    assert "refined_blog" in result
    assert "Original content A." in result["refined_blog"]

@pytest.mark.asyncio
async def test_multiple_products_all_refined():
    """All products in blog get refined."""
    blog_md = """
## Top Picks
### 1. MacBook Air M2
Content A

### 2. ASUS VivoBook 15  
Content B
"""
    mock_signals = {
        "found": True,
        "praise": ["nice"],
        "complaints": [],
    }
    captured_prompts = []
    async def mock_llm(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Refined multi"
    
    with patch('core.post_processors.product_refiner.gather_product_signals',
               new_callable=AsyncMock, return_value=mock_signals):
        with patch('core.post_processors.product_refiner.call_llm',
                   new_callable=AsyncMock, side_effect=mock_llm):
            result = await refine_blog_products(blog_md, "test")
    assert len(captured_prompts) == 2
    assert result["total_products"] == 2
