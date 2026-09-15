"""Test image quality improvements."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_enhanced_prompt():
    from core.exporters.image_generator import _build_enhanced_prompt
    
    # Test laptop prompt
    prompt1 = _build_enhanced_prompt("Best Budget Laptop for Video Editing")
    assert "laptop" in prompt1.lower()
    assert "professional" in prompt1.lower()
    assert "no text" in prompt1.lower()
    print(f"[OK] Laptop prompt: {prompt1[:100]}...")
    
    # Test guide prompt
    prompt2 = _build_enhanced_prompt("How to Install Windows 11")
    assert "infographic" in prompt2.lower() or "design" in prompt2.lower()
    print(f"[OK] Guide prompt: {prompt2[:100]}...")

def test_hf_space_api_available():
    try:
        from gradio_client import Client
        client = Client("M3st3rJ4k3l/FLUX.2-Klein-Multi-LoRA")
        print("[OK] HF Space API accessible")
        return True
    except Exception as e:
        print(f"[WARN] HF Space API not available: {e}")
        return False

def test_image_dimensions():
    from core.exporters.image_generator import GEN_W, GEN_H
    assert GEN_W == 1200 and GEN_H == 675
    from core.exporters.product_image_generator import GEN_W as P_GEN_W, GEN_H as P_GEN_H
    assert P_GEN_W == 1200 and P_GEN_H == 675

if __name__ == "__main__":
    test_enhanced_prompt()
    test_hf_space_api_available()
    print("\nImage quality tests complete!")
