"""Generate high-quality featured images using HF Space API + fallback chain."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import httpx

from app.config import logger, UNISCOLIAN_UPLOADS_DIR

DISPLAY_W, DISPLAY_H = 450, 377
GEN_W, GEN_H = 900, 752  # 2x file resolution for retina sharpness

# HF Space API endpoint
HF_SPACE_NAME = "M3st3rJ4k3l/FLUX.2-Klein-Multi-LoRA"

# Pollinations URL (fallback 3)
POLLINATIONS_URL = ("https://image.pollinations.ai/prompt/{prompt}"
                    "?width=900&height=752&model=flux&nologo=true&seed=7")


def _build_enhanced_prompt(title: str) -> str:
    """Build a detailed, high-quality prompt for better image generation."""
    # Extract key concepts from title
    title_lower = title.lower()
    
    # Topic-specific enhancements
    if any(word in title_lower for word in ["laptop", "computer", "device"]):
        style = "professional product photography, studio lighting, clean background"
        details = "sharp focus, high detail, 8k resolution"
    elif any(word in title_lower for word in ["guide", "tutorial", "how to"]):
        style = "clean infographic style, modern design, professional layout"
        details = "minimalist, educational, clear visual hierarchy"
    elif any(word in title_lower for word in ["review", "comparison", "best"]):
        style = "editorial photography, magazine style, professional composition"
        details = "balanced lighting, sharp details, commercial quality"
    else:
        style = "modern digital illustration, vibrant colors, professional design"
        details = "high quality, detailed, polished finish"
    
    # Core prompt structure
    base = f"high quality {style} for a technology blog article about: {title}"
    negative = "no text, no words, no letters, no watermark, no logo, no signatures"
    
    return f"{base}, {details}. {negative}"


def _hf_space_api(prompt_text: str) -> Optional[bytes]:
    """Generate image using HF Space API (gradio_client) - HIGHEST QUALITY."""
    try:
        from gradio_client import Client
        
        client = Client(HF_SPACE_NAME)
        
        # Call the API with optimized parameters
        # This matches the HF Space's best settings
        result = client.predict(
            prompt=prompt_text,
            negative_prompt="blurry, low quality, distorted, text, watermark, logo",
            seed=42,
            randomize_seed=False,
            num_inference_steps=20,
            guidance_scale=7.5,
            width=GEN_W,
            height=GEN_H,
            api_name="/infer"
        )
        
        # result is a file path or URL
        if isinstance(result, str):
            if result.startswith("http"):
                resp = httpx.get(result, timeout=60)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    return resp.content
            else:
                # Local file path
                with open(result, "rb") as f:
                    return f.read()
        
        return None
    except Exception as e:
        logger.warning("HF Space API failed: %s", e)
        return None


def _hf_flux_inference(prompt_text: str) -> Optional[bytes]:
    """Generate image using HF Inference API (fallback 2)."""
    try:
        import os
        import io
        
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
        if not token:
            return None
        
        from huggingface_hub import InferenceClient
        
        client = InferenceClient(token=token)
        
        # Use FLUX.1-schnell with better parameters
        img = client.text_to_image(
            prompt_text,
            model="black-forest-labs/FLUX.1-schnell",
            width=GEN_W,
            height=GEN_H,
            num_inference_steps=8,  # More steps for better quality
            guidance_scale=7.5      # Higher guidance for better prompt adherence
        )
        
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return buf.getvalue()
    except Exception as e:
        logger.warning("HF Inference API failed: %s", e)
        return None


def _pollinations_api(prompt_text: str) -> Optional[bytes]:
    """Generate image using Pollinations API (fallback 3)."""
    try:
        resp = httpx.get(
            POLLINATIONS_URL.format(prompt=quote(prompt_text)),
            timeout=60,
            follow_redirects=True
        )
        resp.raise_for_status()
        
        if len(resp.content) > 1000:
            return resp.content
        return None
    except Exception as e:
        logger.warning("Pollinations API failed: %s", e)
        return None


def _pil_fallback(title: str, path: Path) -> None:
    """Offline branded placeholder card 900x752 (fallback 4)."""
    from PIL import Image, ImageDraw, ImageFont
    
    img = Image.new("RGB", (GEN_W, GEN_H))
    draw = ImageDraw.Draw(img)
    
    # Gradient background (Uniscolian blue)
    for y in range(GEN_H):
        r = int(24 + (40 - 24) * y / GEN_H)
        g = int(49 + (114 - 49) * y / GEN_H)
        b = int(83 + (250 - 83) * y / GEN_H)
        draw.line([(0, y), (GEN_W, y)], fill=(r, g, b))
    
    # Try to use a nice font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 52)
        small = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
        small = font
    
    # Wrap title (~28 chars per line, max 6 lines)
    words, lines, cur = title.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= 28:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
            if len(lines) == 6:
                break
    if cur and len(lines) < 6:
        lines.append(cur)
    
    # Draw text
    y0 = 240
    for ln in lines:
        draw.text((50, y0), ln, fill=(255, 255, 255), font=font)
        y0 += 68
    
    # Brand watermark
    draw.text((50, 670), "UNISCOLIAN", fill=(200, 220, 255), font=small)
    
    img.save(path, "JPEG", quality=88)


def generate_featured_image(topic: str, title: str, slug: str) -> dict:
    """Create {slug}-featured.jpg (900x752) with high-quality generation."""
    ym = datetime.now().strftime("%Y/%m")
    out_dir = UNISCOLIAN_UPLOADS_DIR / ym
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}-featured.jpg"
    rel = f"wp-content/uploads/{ym}/{slug}-featured.jpg"
    
    # Check if already exists
    if path.exists():
        logger.info("Featured image already exists: %s", path)
        return {
            "status": "exists",
            "source": "manual",
            "relative_path": rel,
            "file_exists": True
        }
    
    # Build enhanced prompt
    prompt = _build_enhanced_prompt(title)
    logger.info("Generating image with prompt: %s", prompt)
    
    # Try generation sources in order of quality
    image_bytes = None
    source = None
    
    # 1. Try HF Space API (best quality)
    image_bytes = _hf_space_api(prompt)
    if image_bytes:
        source = "hf_space"
    
    # 2. Try HF Inference API
    if not image_bytes:
        image_bytes = _hf_flux_inference(prompt)
        if image_bytes:
            source = "hf_inference"
    
    # 3. Try Pollinations API
    if not image_bytes:
        image_bytes = _pollinations_api(prompt)
        if image_bytes:
            source = "pollinations"
    
    # Save if we got image bytes
    if image_bytes:
        from PIL import Image
        import io
        
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Resize to exact 900x752 if needed
        if im.size != (GEN_W, GEN_H):
            im = im.resize((GEN_W, GEN_H), Image.Resampling.LANCZOS)
        im.save(path, "JPEG", quality=90)
        
        logger.info("Featured image generated (%s): %s", source, path)
        return {
            "status": "generated",
            "source": source,
            "relative_path": rel,
            "file_exists": True
        }
    
    # 4. Fallback to PIL
    logger.warning("All APIs failed. Using offline PIL fallback.")
    _pil_fallback(title, path)
    return {
        "status": "generated",
        "source": "pil",
        "relative_path": rel,
        "file_exists": True
    }
