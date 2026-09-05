"""Post-processor to clean heading number prefixes from generated blog content."""
from __future__ import annotations
import re
from typing import List, Dict
from app.config import logger


def clean_heading_numbers(blog_markdown: str) -> str:
    """Remove number prefixes (1., 2., 3., etc.) from all H2 and H3 headings.
    
    Examples:
    - "### 1. The Best Overall" → "### The Best Overall"
    - "## 2. Products at a Glance" → "## Products at a Glance"
    - "### Best Value Pick" → "### Best Value Pick" (no change)
    """
    if not blog_markdown:
        return blog_markdown
    
    # Pattern: ## or ### followed by optional whitespace, then a number with . or ), then whitespace
    pattern = r'^(#{2,3})\s*\d+[\.\)]\s*'
    
    cleaned_lines = []
    changes_made = 0
    
    for line in blog_markdown.split('\n'):
        if line.startswith('##') or line.startswith('###'):
            cleaned_line = re.sub(pattern, r'\1 ', line, flags=re.MULTILINE)
            if cleaned_line != line:
                changes_made += 1
            cleaned_lines.append(cleaned_line)
        else:
            cleaned_lines.append(line)
    
    if changes_made > 0:
        logger.info(f"Cleaned {changes_made} heading number prefixes")
    
    return '\n'.join(cleaned_lines)


def clean_section_content(content: str) -> str:
    """Clean number prefixes from a single section's content."""
    return clean_heading_numbers(content)
