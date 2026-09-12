"""Export-level verification test for product image and affiliate button placement."""
import os
import shutil
import re
import inspect
import pytest
from pathlib import Path
from PIL import Image
import io

from app.config import UNISCOLIAN_ROOT, CONTENT_OUTPUT_DIR
import app.gradio_app
from core.exporters.product_image_generator import generate_all_product_images
from core.exporters.static_exporter import export_post_to_uniscolian


PRODUCTS = [
    "ASUS ROG Crosshair X870E Hero",
    "MSI MPG X870E CARBON WIFI",
    "GIGABYTE X870 AORUS ELITE WIFI7",
    "ASUS TUF GAMING X870-PLUS WIFI",
    "ASRock B650E Steel Legend WiFi",
    "GIGABYTE B650 EAGLE AX"
]

LINKS = {name: f"https://affiliate.example/{i}" for i, name in enumerate(PRODUCTS, 1)}


def _tiny_jpeg() -> bytes:
    buf = io.BytesIO()
    im = Image.new("RGB", (64, 64), color="blue")
    im.save(buf, "JPEG", quality=90)
    data = buf.getvalue()
    if len(data) < 5000:
        data = data + b"\x00" * (5001 - len(data))
    return data


def _sample_markdown() -> str:
    lines = [
        "# Best Motherboards 2026",
        "",
        "## Introduction",
        "Here is the introduction to the best motherboards of 2026 for high-end gaming and productivity.",
        "",
        "## At a Glance: Quick Comparison of Top Picks",
        "",
        "| Product | Tier | Buy |",
        "|---|---|---|",
    ]
    for i, name in enumerate(PRODUCTS, 1):
        lines.append(f"| {name} | Premium | [Buy]({LINKS[name]}) |")
    
    lines.extend([
        "",
        "## Detailed Product Reviews",
        ""
    ])

    for name in PRODUCTS:
        lines.extend([
            f"### {name}",
            f"This is the first review paragraph for {name} detailing performance, VRM, and features.",
            "#### Key Specifications",
            f"- VRM and memory support details for {name}.",
            "#### Pros & Cons",
            "Pros: great value. Cons: none major.",
            f"This is the final review paragraph for {name} with final thoughts, comprehensive testing notes, and detailed specifications for building an ultimate rig with long-term stability and performance headroom, ensuring you get maximum value and exceptional overclocking potential across all demanding workloads and future upgrades without any performance bottlenecks or thermal throttling.",
            ""
        ])

    lines.extend([
        "## Buying Guide",
        "How to choose the right motherboard for your specific CPU and memory needs.",
        "",
        "## FAQ",
        "Frequently asked questions about AM5 motherboards.",
        "",
        "## Conclusion",
        "Final thoughts on building your next gaming rig."
    ])

    return "\n".join(lines)


def test_exported_html_placement():
    post_dir = UNISCOLIAN_ROOT / "html-placement-test"
    if post_dir.exists():
        shutil.rmtree(post_dir, ignore_errors=True)

    from unittest.mock import patch
    with patch("core.exporters.product_image_generator.generate_product_image_bytes", return_value=(_tiny_jpeg(), "mock")):
        updated_md, report = generate_all_product_images(
            markdown=_sample_markdown(),
            slug="html-placement-test",
            category="motherboard",
            output_dir=UNISCOLIAN_ROOT,
            selected_products=[{"name": n} for n in PRODUCTS]
        )

    images_map = {r["product_name"]: r["rel_path"] for r in report if r["status"] == "success"}
    assert len(images_map) == 6, f"Expected 6 images generated, got {len(images_map)}"

    export_post_to_uniscolian(
        markdown=updated_md,
        topic="html-placement-test",
        category_name="Motherboards",
        category_slug="motherboards",
        generate_image=False,
        update_sitemap=False,
        avoid_duplicates=False,
        product_affiliate_links=LINKS,
        product_images_map=images_map,
    )

    index_html = post_dir / "index.html"
    assert index_html.exists(), f"Exported HTML index.html not found at {index_html}"
    html = index_html.read_text(encoding="utf-8")

    print("\n" + "=" * 80)
    print("📋 EXPORT PLACEMENT AUDIT TABLE")
    print(f"{'Product':<35} | {'Img Pos':<8} | {'H3 Pos':<8} | {'Btn Pos':<8} | {'Next H Pos':<10} | {'Exists':<6}")
    print("-" * 80)

    audit_rows = []
    h3_positions = {}

    for name in PRODUCTS:
        # Find h3 for product robustly
        all_h3 = list(re.finditer(r'<h3[^>]*>.*?</h3>', html, re.DOTALL | re.IGNORECASE))
        h3_match = next((m for m in all_h3 if name in m.group(0)), None)
        assert h3_match, f"Product '{name}': H3 heading not found in HTML"
        h3_pos = h3_match.start()
        h3_positions[name] = h3_pos

        all_headings_after = list(re.finditer(r'<(h2|h3)', html[h3_pos + len(h3_match.group(0)):]))
        if all_headings_after:
            next_heading_pos = h3_pos + len(h3_match.group(0)) + all_headings_after[0].start()
        else:
            next_heading_pos = len(html)

        section = html[h3_pos:next_heading_pos]

        # R1: Image immediately after H3 (h3_tag_end < img_pos < next_heading_pos, first 30% of section, img_pos < btn_pos)
        all_imgs = list(re.finditer(r'<img\s+[^>]*class="product-image"[^>]*>', html))
        valid_imgs = [m for m in all_imgs if h3_pos < m.start() < next_heading_pos and f'alt="{name} product photo"' in m.group(0)]
        assert valid_imgs, f"Product '{name} (R1)': Image tag for '{name}' not found after H3"
        img_match = min(valid_imgs, key=lambda m: m.start())
        img_pos = img_match.start()

        h3_tag_end_match = re.search(r'</h3>', html[h3_pos:])
        assert h3_tag_end_match, f"Product '{name} (R1)': H3 tag end not found"
        h3_tag_end = h3_pos + h3_tag_end_match.end()

        assert h3_tag_end < img_pos < next_heading_pos, f"Product '{name} (R1)': Image position ({img_pos}) must be between H3 tag end ({h3_tag_end}) and next heading ({next_heading_pos})"

        intervening = html[h3_tag_end:img_pos]
        assert "<h2" not in intervening and "<h3" not in intervening, f"Product '{name} (R1)': Intervening headings found between H3 tag end and image: {intervening}"

        section_len = next_heading_pos - h3_pos
        img_offset_in_sec = img_pos - h3_pos
        thirty_percent_mark = int(section_len * 0.3)
        assert img_offset_in_sec <= thirty_percent_mark, f"Product '{name} (R1)': Image position offset ({img_offset_in_sec}) must be in the first 30% of the section (<= {thirty_percent_mark}, section length {section_len})"

        # R2: Affiliate button at the end of section (before next heading, after last H4, within last 25%)
        h4_matches = list(re.finditer(r'<h4', section))
        last_h4_pos_in_sec = h4_matches[-1].start() if h4_matches else 0

        link_val = LINKS[name]
        link_pos_in_sec = section.find(link_val)
        assert link_pos_in_sec != -1, f"Product '{name} (R2)': Affiliate link {link_val} not found in product section"
        
        assert link_pos_in_sec > last_h4_pos_in_sec, f"Product '{name} (R2)': Affiliate button position must be after the last H4 heading"

        section_len = len(section)
        twenty_five_percent_mark = section_len - (section_len // 4)
        assert link_pos_in_sec >= twenty_five_percent_mark, f"Product '{name} (R2)': Affiliate button position ({link_pos_in_sec}) must be within the last 25% of the section (>= {twenty_five_percent_mark}, section length {section_len})"

        btn_pos = h3_pos + link_pos_in_sec
        assert img_pos < btn_pos, f"Product '{name} (R1)': Image position ({img_pos}) must be before button position ({btn_pos})"

        # R4: Image file exists on disk
        src_match = re.search(r'src="([^"]+)"', img_match.group(0))
        assert src_match, f"Product '{name} (R4)': src attribute not found in image tag"
        src_rel = src_match.group(1)
        img_file_path = (post_dir / src_rel).resolve()
        file_exists = img_file_path.exists()
        assert file_exists, f"Product '{name} (R4)': Referenced image file does not exist on disk at {img_file_path}"

        # R3: Affiliate link shown in product table
        table_match = re.search(r'<figure class="wp-block-table">.*?</figure>', html, re.DOTALL)
        assert table_match, f"Product '{name} (R3)': Comparison table not found in HTML"
        table_block = table_match.group(0)
        assert link_val in table_block, f"Product '{name} (R3)': Affiliate link {link_val} not found in comparison table"

        audit_rows.append((name, img_pos, h3_pos, btn_pos, next_heading_pos, file_exists))
        print(f"{name[:34]:<35} | {img_pos:<8} | {h3_pos:<8} | {btn_pos:<8} | {next_heading_pos:<10} | {str(file_exists):<6}")

    print("-" * 80)
    assert html.count('class="product-image"') == 6, f"Expected exactly 6 product-image classes, found {html.count('class=\"product-image\"')}"

    # R1b: Assert every product image is wrapped exactly like the featured image wrapper
    figure_pattern = r'<figure class="wp-block-image aligncenter size-full is-resized"><img[^>]*class="product-image"[^>]*style="width:450px;max-width:100%;height:auto;">\s*</figure>'
    figure_matches = list(re.finditer(figure_pattern, html))
    assert len(figure_matches) == 6, f"Expected 6 product image figure wrappers matching featured style, found {len(figure_matches)}"

    all_h2 = list(re.finditer(r'<h2[^>]*>.*?</h2>', html, re.DOTALL | re.IGNORECASE))
    h2_match = next((m for m in all_h2 if "Buying Guide" in m.group(0)), None)
    assert h2_match, "H2 'Buying Guide' heading not found in HTML"
    buying_guide_pos = h2_match.start()
    last_product_name = PRODUCTS[-1]
    last_h3_pos = h3_positions[last_product_name]
    last_section_content = html[last_h3_pos:buying_guide_pos]
    assert LINKS[last_product_name] in last_section_content, f"Last product ({last_product_name}) affiliate button must be inside the last section before 'Buying Guide'"

    # Print proof snippet around two consecutive products showing order = heading, figure, content, button, next heading
    print("\n🔍 PROOF SNIPPET (First two product sections in HTML):")
    p1_pos = h3_positions[PRODUCTS[0]]
    p3_h3_match = next((m for m in all_h3 if PRODUCTS[2] in m.group(0)), None)
    p3_pos = p3_h3_match.start() if p3_h3_match else len(html)
    print(html[p1_pos:p3_pos])
    print("=" * 80)

    print(f"\n📂 Exported HTML absolute path: {index_html.resolve()}")


def test_ui_action_saves_into_uniscolian_root():
    src = inspect.getsource(app.gradio_app.generate_all_product_images_action)
    assert "output_dir=UNISCOLIAN_ROOT" in src, f"generate_all_product_images_action must use output_dir=UNISCOLIAN_ROOT, found source: {src}"
