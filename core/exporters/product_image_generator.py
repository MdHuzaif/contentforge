"""Product Image Generation module using Cloudflare Workers AI (Flux-1-Schnell) and Pollinations fallback."""
from __future__ import annotations
import os
import re
import time
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import quote
import httpx
from PIL import Image
import io

logger = logging.getLogger("contentforge")

GEN_W, GEN_H = 900, 752

GENERIC_HEADINGS = {
    "introduction", "conclusion", "buying guide", "faq", "frequently asked",
    "at a glance", "quick comparison", "key specifications", "performance",
    "verdict", "final thoughts", "recommendations", "how to", "what is",
    "why", "pros", "cons", "tier breakdown", "common mistakes", "future-proofing"
}


def ensure_env_loaded():
    """Idempotent .env loader using python-dotenv."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _normalize_text(text: str) -> str:
    """Normalize product name or heading for robust matching."""
    if not text:
        return ""
    t = text.lower()
    t = t.replace("wi-fi", "wifi")
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _cloudflare_workers_ai(prompt: str) -> Tuple[Optional[bytes], str]:
    """Generate image using Cloudflare Workers AI (Flux-1-Schnell)."""
    ensure_env_loaded()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()

    if not account_id or not api_token:
        logger.info("   ⚠️ Cloudflare credentials not found in environment")
        return None, "none"

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "steps": 4,
    }

    try:
        logger.info(f"   Connecting to Cloudflare Workers AI: {url}")
        resp = httpx.post(url, headers=headers, json=payload, timeout=60)
        
        if resp.status_code in (402, 429, 503):
            logger.warning(f"   ⚠️ Cloudflare HTTP status {resp.status_code}, returning None")
            return None, "none"
            
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()
        if content_type.startswith("image/"):
            raw_bytes = resp.content
        else:
            data = resp.json()
            res_dict = data.get("result", {})
            b64_str = res_dict.get("image") or data.get("image")
            if not b64_str:
                return None, "none"
            raw_bytes = base64.b64decode(b64_str)

        if len(raw_bytes) > 5000 and raw_bytes.startswith(b"\xff\xd8"):
            return raw_bytes, "cloudflare"
        
        return None, "none"
    except Exception as e:
        logger.warning(f"   ✗ Cloudflare Workers AI error: {type(e).__name__}: {e}")
        return None, "none"


def _pollinations_product(prompt: str, width: int = 900, height: int = 752) -> Tuple[Optional[bytes], str]:
    """Generate image using Pollinations API with parameterized dimensions."""
    try:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width={width}&height={height}&model=flux&nologo=true&seed=7"
        resp = httpx.get(url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        
        if len(resp.content) > 5000 and resp.content.startswith(b"\xff\xd8"):
            return resp.content, "pollinations"
        elif len(resp.content) > 1000:
            return resp.content, "pollinations"
        return None, "none"
    except Exception as e:
        logger.warning(f"Pollinations product API failed: {e}")
        return None, "none"


def generate_product_image_bytes(prompt: str, width: int = 900, height: int = 752) -> Tuple[Optional[bytes], str]:
    """Chain: Cloudflare FIRST, Pollinations SECOND. Returns (bytes, source)."""
    ensure_env_loaded()
    
    # 1. Cloudflare Workers AI
    cf_bytes, cf_source = _cloudflare_workers_ai(prompt)
    if cf_bytes:
        logger.info("✓ Product image successfully generated via Cloudflare Workers AI")
        return cf_bytes, cf_source

    # 2. Pollinations
    poll_bytes, poll_source = _pollinations_product(prompt, width, height)
    if poll_bytes:
        logger.info("✓ Product image successfully generated via Pollinations")
        return poll_bytes, poll_source

    logger.warning("✗ All product image sources failed.")
    return None, "none"


def build_product_image_prompt(product_name: str, category: str, tier: str = "mid_range") -> str:
    """Build high-quality product photography prompt with strict negative guard."""
    tier_desc = {
        "premium": "luxury high-end premium flagship",
        "mid_range": "balanced performance modern consumer",
        "budget": "cost-effective value-oriented minimalist"
    }.get(tier, "modern professional")

    base = f"editorial magazine-style professional product photography of {product_name}, a {tier_desc} {category}"
    details = "studio lighting, clean neutral background, sharp focus, 8k resolution, commercial product showcase"
    guard = "NO text, NO words, NO letters, NO watermark, NO logo, NO captions, NO labels, NO typography, NO brand names"
    return f"{base}, {details}. {guard}"


def detect_product_headings(markdown: str, selected_products: List[Any]) -> List[dict]:
    """Detect H2/H3 headings corresponding to selected products."""
    if not markdown or not selected_products:
        return []

    products_map = {}
    for p in selected_products:
        if isinstance(p, dict):
            name = p.get("name", "").strip()
        else:
            name = str(p).strip()
        if name:
            norm_name = _normalize_text(name)
            if norm_name:
                products_map[norm_name] = name

    if not products_map:
        return []

    lines = markdown.split("\n")
    detected = []
    matched_product_names = set()
    # Sort products by length descending so longer product names match first
    sorted_products = sorted(products_map.items(), key=lambda x: len(x[0]), reverse=True)

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("##"):
            continue
        if "|" in stripped:
            continue

        if stripped.startswith("### "):
            level = "###"
            raw_heading = stripped[3:].strip()
        elif stripped.startswith("## "):
            level = "##"
            raw_heading = stripped[3:].strip()
        elif stripped.startswith("###"):
            level = "###"
            raw_heading = stripped[3:].strip()
        elif stripped.startswith("##"):
            level = "##"
            raw_heading = stripped[2:].strip()
        else:
            continue

        norm_heading = _normalize_text(raw_heading)

        if norm_heading in GENERIC_HEADINGS:
            continue
        if any(g in norm_heading for g in ["introduction", "conclusion", "buying guide", "frequently asked", "at a glance"]):
            continue

        for norm_p, orig_p in sorted_products:
            if orig_p in matched_product_names:
                continue
            
            if norm_p == norm_heading or (len(norm_p) >= 5 and norm_p in norm_heading):
                matched_product_names.add(orig_p)
                detected.append({
                    "name": orig_p,
                    "heading_text": raw_heading,
                    "level": level,
                    "position": idx,
                })
                break

    return detected


def inject_product_images_into_markdown(markdown: str, images_map: Dict[str, str]) -> str:
    """Insert product image figure immediately AFTER the matched heading line."""
    if not markdown or not images_map:
        return markdown

    lines = markdown.split("\n")
    result_lines = []
    
    sorted_items = sorted(images_map.items(), key=lambda x: len(x[0]), reverse=True)

    for line in lines:
        stripped = line.strip()
        result_lines.append(line)

        if stripped.startswith("##") and "|" not in stripped:
            if stripped.startswith("### "):
                raw_heading = stripped[3:].strip()
            elif stripped.startswith("## "):
                raw_heading = stripped[3:].strip()
            elif stripped.startswith("###"):
                raw_heading = stripped[3:].strip()
            elif stripped.startswith("##"):
                raw_heading = stripped[2:].strip()
            else:
                raw_heading = ""

            norm_h = _normalize_text(raw_heading)
            
            matched_rel_path = None
            matched_name = raw_heading
            for orig_k, rel_p in sorted_items:
                norm_k = _normalize_text(orig_k)
                if norm_k == norm_h or (len(norm_k) >= 5 and norm_k in norm_h):
                    matched_rel_path = rel_p
                    matched_name = orig_k
                    break

            if matched_rel_path:
                tag = (
                    '<figure class="wp-block-image aligncenter size-full is-resized">'
                    f'<img decoding="async" width="450" height="377" src="{matched_rel_path}" srcset="{matched_rel_path} 2x" '
                    f'alt="{matched_name} product photo" class="product-image" loading="lazy" '
                    'style="width:450px;max-width:100%;height:auto;">'
                    '</figure>'
                )
                result_lines.append("")
                result_lines.append(tag)

    return "\n".join(result_lines)


def _crop_resize(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop to target aspect ratio first, then LANCZOS resize."""
    orig_w, orig_h = im.size
    target_aspect = target_w / target_h
    orig_aspect = orig_w / orig_h

    if orig_aspect > target_aspect:
        new_w = int(orig_h * target_aspect)
        offset = (orig_w - new_w) // 2
        crop_box = (offset, 0, offset + new_w, orig_h)
    else:
        new_h = int(orig_w / target_aspect)
        offset = (orig_h - new_h) // 2
        crop_box = (0, offset, orig_w, offset + new_h)

    cropped = im.crop(crop_box)
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)


def generate_all_product_images(
    markdown: str,
    slug: str,
    category: str,
    output_dir: Path | str,
    selected_products: List[Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Detect product headings, generate product images, save files, and inject into markdown."""
    output_path = Path(output_dir)
    now = datetime.now()
    uploads_ym = now.strftime("%Y/%m")
    timestamp_str = now.strftime("%Y%m%d-%H%M%S")

    detected = detect_product_headings(markdown, selected_products)
    if not detected:
        return markdown, []

    images_map = {}
    report = []
    uploads_dir = output_path / "wp-content" / "uploads" / uploads_ym
    uploads_dir.mkdir(parents=True, exist_ok=True)

    for i, det in enumerate(detected, 1):
        name = det["name"]
        heading = det["heading_text"]
        
        tier = "mid_range"
        for p in selected_products:
            if isinstance(p, dict) and p.get("name") == name:
                tier = p.get("tier", "mid_range")
                break

        prompt = build_product_image_prompt(name, category, tier)
        logger.info(f"🎨 Generating product image {i}/{len(detected)} for '{name}'...")

        img_bytes, source = generate_product_image_bytes(prompt)
        
        file_name = f"{slug}-product-{i}-{timestamp_str}.jpg"
        file_path = uploads_dir / file_name
        rel_path = f"../wp-content/uploads/{uploads_ym}/{file_name}"

        if img_bytes:
            try:
                im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                im = _crop_resize(im, GEN_W, GEN_H)
                im.save(file_path, "JPEG", quality=90)
                
                images_map[name] = rel_path
                report.append({
                    "product_name": name,
                    "heading": heading,
                    "rel_path": rel_path,
                    "source": source,
                    "status": "success",
                })
                logger.info(f"✓ Saved product image ({source}) to {file_path}")
            except Exception as e:
                logger.warning(f"Failed to save image bytes for '{name}': {e}")
                report.append({
                    "product_name": name,
                    "heading": heading,
                    "rel_path": "",
                    "source": "none",
                    "status": "failed",
                })
        else:
            logger.warning(f"⚠️ Image generation failed for '{name}' (status=failed)")
            report.append({
                "product_name": name,
                "heading": heading,
                "rel_path": "",
                "source": "none",
                "status": "failed",
            })

        if i < len(detected):
            time.sleep(3)

    updated_markdown = inject_product_images_into_markdown(markdown, images_map)
    return updated_markdown, report
