"""Live export test for Product Image Generation."""
import os
import pytest
from pathlib import Path
import httpx

from core.exporters.product_image_generator import (
    generate_all_product_images,
    ensure_env_loaded,
)
from app.config import CONTENT_OUTPUT_DIR


def test_cloudflare_live_export():
    ensure_env_loaded()
    cf_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN")

    # Check if Pollinations is reachable if credentials are missing
    pollinations_reachable = False
    try:
        resp = httpx.get("https://image.pollinations.ai/prompt/test?width=100&height=100", timeout=10)
        if resp.status_code == 200:
            pollinations_reachable = True
    except Exception:
        pass

    if not cf_id or not cf_token:
        if not pollinations_reachable:
            pytest.skip("Cloudflare credentials missing and Pollinations unreachable. Skipping live test.")

    sample_markdown = """# Ultimate AMD AM5 Motherboard Roundup 2026

Welcome to our comprehensive guide on the best AMD AM5 motherboards for high-performance computing and gaming builds.

### ASUS ROG Crosshair X870E Hero
The ASUS ROG Crosshair X870E Hero is a flagship motherboard designed for enthusiasts who demand extreme overclocking capabilities, robust power delivery, and cutting-edge connectivity features like Wi-Fi 7 and USB4.

### MSI MPG X870E CARBON WIFI
Offering an incredible balance of aesthetics and thermals, the MSI MPG X870E CARBON WIFI caters to high-end gamers and creators looking for reliable multi-core performance and sleek dark styling.

### Gigabyte B650 EAGLE AX
The Gigabyte B650 EAGLE AX provides exceptional value for budget-conscious builders who still want solid VRMs, DDR5 support, and stable everyday performance without breaking the bank.

## Conclusion
Choose the board that fits your tier and budget.
"""

    selected_products = [
        {"name": "ASUS ROG Crosshair X870E Hero", "tier": "premium"},
        {"name": "MSI MPG X870E CARBON WIFI", "tier": "mid_range"},
        {"name": "Gigabyte B650 EAGLE AX", "tier": "budget"},
    ]

    output_review_dir = CONTENT_OUTPUT_DIR / "product_image_review"
    output_review_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("🚀 RUNNING LIVE PRODUCT IMAGE GENERATION EXPORT TEST")
    print(f"   Output Directory: {output_review_dir}")
    print("=" * 80)

    updated_md, report = generate_all_product_images(
        markdown=sample_markdown,
        slug="am5-motherboards-2026",
        category="motherboard",
        output_dir=output_review_dir,
        selected_products=selected_products,
    )

    # Build report.md table
    report_lines = [
        "# Product Image Generation Review Report",
        "",
        "| Product | Heading | Source | File | Size(KB) |",
        "|---|---|---|---|---|"
    ]

    print("\n📊 Generation Report:")
    for r in report:
        p_name = r["product_name"]
        heading = r["heading"]
        source = r["source"]
        status = r["status"]
        rel_path = r["rel_path"]
        
        size_kb = "N/A"
        file_abs = ""
        if status == "success" and rel_path:
            rel_part = rel_path.replace("../", "")
            file_abs = output_review_dir / rel_part
            if file_abs.exists():
                size_kb = f"{file_abs.stat().st_size / 1024:.1f} KB"
                print(f"  - [{status.upper()}] {p_name} -> Absolute Path: {file_abs.resolve()}")
            else:
                print(f"  - [{status.upper()}] {p_name} -> Path: {rel_path}")
        else:
            print(f"  - [FAILED] {p_name}")

        report_lines.append(f"| {p_name} | {heading} | {source} | `{rel_path}` | {size_kb} |")

    report_md_path = output_review_dir / "report.md"
    report_md_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n📝 Report written to: {report_md_path.resolve()}")
    print("=" * 80)

    assert len(report) == 3
    assert any(r["status"] == "success" for r in report)


if __name__ == "__main__":
    test_cloudflare_live_export()
