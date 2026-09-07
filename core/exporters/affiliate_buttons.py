"""Amazon affiliate button rendering for Uniscolian export."""
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger("contentforge")

# Affiliate button HTML template
BUTTON_HTML_TEMPLATE = """
<div class="affiliate-button-wrapper">
    <a href="{url}" 
       target="_blank" 
       rel="noopener noreferrer sponsored nofollow"
       class="amazon-affiliate-btn"
       data-product="{product_name}">
        <span class="btn-icon">🛒</span>
        <span class="btn-text">Check Price on Amazon</span>
        <span class="btn-arrow">→</span>
    </a>
    <div class="affiliate-disclosure-small">*As an Amazon Associate, we earn from qualifying purchases.</div>
</div>
"""

# Best Deal badge variant (for top picks)
BEST_DEAL_HTML_TEMPLATE = """
<div class="affiliate-button-wrapper best-deal">
    <div class="best-deal-badge">⭐ Best Deal</div>
    <a href="{url}" 
       target="_blank" 
       rel="noopener noreferrer sponsored nofollow"
       class="amazon-affiliate-btn best-deal-btn"
       data-product="{product_name}">
        <span class="btn-icon">🛒</span>
        <span class="btn-text">Check Current Deal on Amazon</span>
        <span class="btn-arrow">→</span>
    </a>
    <div class="affiliate-disclosure-small">*As an Amazon Associate, we earn from qualifying purchases.</div>
</div>
"""

# Compact button for tables (At a Glance)
TABLE_BUTTON_HTML = """<a href="{url}" target="_blank" rel="noopener noreferrer sponsored nofollow" class="amazon-btn-table">🛒 Buy</a>"""


def render_affiliate_button(
    product_name: str,
    amazon_url: Optional[str],
    is_top_pick: bool = False,
    compact: bool = False,
) -> str:
    """Render affiliate button HTML. Accept ANY URL."""
    if not amazon_url or not amazon_url.strip():
        return ""
    
    # Accept ANY URL - no validation
    url = amazon_url.strip()
    
    if compact:
        return TABLE_BUTTON_HTML.format(url=url, product_name=product_name)
    
    if is_top_pick:
        return BEST_DEAL_HTML_TEMPLATE.format(url=url, product_name=product_name)
    
    return BUTTON_HTML_TEMPLATE.format(url=url, product_name=product_name)


def inject_buttons_into_markdown(
    markdown_content: str,
    product_links: Dict[str, str],
    top_pick_product: Optional[str] = None,
) -> str:
    """Inject affiliate buttons into markdown content:
    1. After conclusion/verdict in each product section (H3 with product name)
    2. In the 'At a Glance' comparison table
    """
    if not product_links:
        return markdown_content
    
    result = markdown_content
    
    # === STEP 1: Inject buttons after product detail sections ===
    for product_name, url in product_links.items():
        is_top = (top_pick_product and product_name == top_pick_product)
        button_html = render_affiliate_button(product_name, url, is_top_pick=is_top)
        
        if not button_html:
            continue
        
        # Try multiple patterns with fuzzy matching
        escaped_name = re.escape(product_name)
        
        # Pattern 1: Exact match
        pattern1 = rf'(### [^\n]*{escaped_name}[^\n]*\n)((?:(?!^#{2,3} ).*\n?)*?)(?=(?:^#{2,3} |\Z))'
        
        # Pattern 2: H2 heading
        pattern2 = rf'(## [^\n]*{escaped_name}[^\n]*\n)((?:(?!^## ).*\n?)*?)(?=(?:^## |\Z))'
        
        # Pattern 3: Fuzzy match (product name appears anywhere in heading)
        keywords = [kw for kw in product_name.split() if len(kw) > 2]
        if keywords:
            keyword_pattern = '|'.join(re.escape(kw) for kw in keywords[:3])  # Top 3 keywords
            pattern3 = rf'(#{2,3} [^\n]*(?:{keyword_pattern})[^\n]*\n)((?:(?!^#{2,3} ).*\n?)*?)(?=(?:^#{2,3} |\Z))'
        else:
            pattern3 = None
        
        match = None
        for pattern in [pattern1, pattern2, pattern3]:
            if pattern is None:
                continue
            match = re.search(pattern, result, re.MULTILINE | re.IGNORECASE)
            if match:
                break
        
        if match:
            heading = match.group(1)
            content = match.group(2)
            
            # Check if button already exists
            if "amazon-affiliate-btn" not in content:
                # INTELLIGENT PLACEMENT: Find conclusion/verdict section
                # Look for patterns like "### Verdict", "### Conclusion", "### Who Should Buy"
                conclusion_patterns = [
                    r'(### [^\n]*(?:Verdict|Conclusion|Who Should Buy|Final Thoughts)[^\n]*\n[^\n]*(?:\n[^\n#][^\n]*)*)',
                    r'(\*\*Verdict[^\n]*\*\*[^\n]*(?:\n[^\n#][^\n]*)*)',
                    r'(\*\*Conclusion[^\n]*\*\*[^\n]*(?:\n[^\n#][^\n]*)*)',
                ]
                
                conclusion_match = None
                for c_pattern in conclusion_patterns:
                    conclusion_match = re.search(c_pattern, content, re.MULTILINE | re.IGNORECASE)
                    if conclusion_match:
                        break
                
                if conclusion_match:
                    # Insert button AFTER the conclusion section
                    conclusion_text = conclusion_match.group(1)
                    new_content = content.replace(
                        conclusion_text,
                        conclusion_text.rstrip() + "\n\n" + button_html + "\n\n"
                    )
                else:
                    # Fallback: Append button at the end of the section
                    new_content = content.rstrip() + "\n\n" + button_html + "\n\n"
                
                result = result.replace(heading + content, heading + new_content, 1)
                logger.info(f"✓ Injected affiliate button for '{product_name}'")
        else:
            logger.warning(f"⚠️ Could not find section for product '{product_name}' - button not injected")
    
    # === STEP 2: Enhance 'At a Glance' table ===
    result = _enhance_at_a_glance_table(result, product_links)
    
    return result


def _enhance_at_a_glance_table(markdown: str, product_links: Dict[str, str]) -> str:
    """Add a 'Buy' column to At a Glance table with affiliate buttons."""
    lines = markdown.split("\n")
    result_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        if line.strip().startswith("|") and line.strip().endswith("|") and i + 1 < len(lines):
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(r'\|\s*[-:]+\s*\|', next_line):
                table_start = i
                table_rows = [line]
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    table_rows.append(lines[j])
                    j += 1
                
                table_text = "\n".join(table_rows)
                has_product = any(p_name in table_text for p_name in product_links.keys())
                
                if has_product and len(table_rows) >= 3:
                    enhanced_rows = []
                    for row_idx, row in enumerate(table_rows):
                        cells = [c.strip() for c in row.split("|")]
                        cells = [c for c in cells if c != ""]
                        
                        if row_idx == 0:
                            enhanced_rows.append("| " + " | ".join(cells) + " | Buy |")
                        elif row_idx == 1:
                            enhanced_rows.append("|" + "|".join([" :---: " for _ in cells]) + "| :---: |")
                        else:
                            row_text = " ".join(cells)
                            button_cell = ""
                            for product_name, url in product_links.items():
                                if product_name.lower() in row_text.lower():
                                    button_cell = render_affiliate_button(
                                        product_name, url, compact=True
                                    )
                                    break
                            enhanced_rows.append("| " + " | ".join(cells) + " | " + button_cell + " |")
                    
                    result_lines.extend(enhanced_rows)
                    i = j
                    continue
        
        result_lines.append(line)
        i += 1
    
    return "\n".join(result_lines)


def generate_disclosure_footer() -> str:
    """Generate Amazon affiliate disclosure for blog footer."""
    return """
---

<div class="affiliate-disclosure-footer">
<strong>Affiliate Disclosure:</strong> As an Amazon Associate, we earn from qualifying purchases. 
Some links in this article are affiliate links, meaning we may earn a small commission at no 
additional cost to you if you make a purchase. This helps support our in-depth testing and 
review process. We only recommend products we genuinely believe in.
</div>
"""
