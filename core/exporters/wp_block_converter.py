"""Convert ContentForge Markdown into Uniscolian (WordPress Blocksy) markup."""
from __future__ import annotations
import re
from datetime import datetime
from typing import Dict, List, Tuple


def slugify_anchor(text: str) -> str:
    """Anchor ids like the reference site: spaces->underscores, keep alnum/_/-."""
    t = text.strip()
    t = re.sub(r'[^0-9A-Za-z _\-]', '', t)
    return re.sub(r'\s+', '_', t)


def strip_heading_number(text: str) -> str:
    """Remove leading numbering like '1. ', '2. ', '10. ' from heading text."""
    return re.sub(r'^\s*\d+\.\s*', '', text)


def _inline(text: str) -> str:
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2" target="_blank" rel="noreferrer noopener">\1</a>', text)
    return text


def convert_markdown_to_wp_blocks(md: str, uploads_ym: str) -> Tuple[str, List[Dict], List[Tuple[int, str]]]:
    """
    Returns (body_html, expected_images, headings).
    expected_images = [{"filename":..., "relative_path":..., "alt":..., "role":...}]
    headings = [(level, text), ...]
    """
    lines = md.split("\n")
    out: List[str] = []
    images: List[Dict] = []
    headings: List[Tuple[int, str]] = []   # for TOC (level 2 & 3)

    i = 0
    n = len(lines)

    def flush_para(buf: List[str]):
        if buf:
            out.append("<p>" + _inline(" ".join(buf).strip()) + "</p>")
            buf.clear()

    para: List[str] = []

    while i < n:
        line = lines[i].rstrip()

        # --- headings ---
        m = re.match(r'^(#{1,4})\s+(.*)$', line)
        if m:
            flush_para(para)
            level = len(m.group(1)); raw_text = m.group(2).strip()
            text = strip_heading_number(raw_text)
            if level == 1:
                i += 1; continue   # H1 handled by hero title, skip in body
            anchor = slugify_anchor(text)
            if level in (2, 3):
                headings.append((level, text))
            tag = f"h{level}"
            out.append(
                f'<{tag} class="wp-block-heading"><span class="ez-toc-section" id="{anchor}"></span>'
                f'<strong>{_inline(text)}</strong><span class="ez-toc-section-end"></span></{tag}>'
            )
            i += 1; continue

        # --- hr ---
        if re.match(r'^-{3,}\s*$', line):
            flush_para(para)
            out.append('<hr class="wp-block-separator has-alpha-channel-opacity">')
            i += 1; continue

        # --- image ---
        m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$', line)
        if m:
            flush_para(para)
            alt, fname = m.group(1), m.group(2).split("/")[-1]
            rel = f"wp-content/uploads/{uploads_ym}/{fname}"
            images.append({"filename": fname, "relative_path": rel, "alt": alt, "role": "inline"})
            out.append(
                f'<figure class="wp-block-image aligncenter size-full is-resized">'
                f'<img decoding="async" width="450" height="377" src="./../{rel}" srcset="./../{rel} 2x" '
                f'alt="{alt}" class="wp-image-1126" loading="lazy" '
                f'style="width:450px;max-width:100%;height:auto;">'
                f'<figcaption class="wp-element-caption">📷 {alt} — <code>{rel}</code></figcaption></figure>'
            )
            i += 1; continue

        # --- blockquote (collect consecutive '> ' lines) ---
        if line.startswith("> "):
            flush_para(para)
            q: List[str] = []
            while i < n and lines[i].startswith("> "):
                q.append(lines[i][2:].strip()); i += 1
            inner = _inline(" ".join(q))
            out.append(f'<blockquote class="wp-block-quote"><p>{inner}</p></blockquote>')
            continue

        # --- lists (ul / ol) ---
        if re.match(r'^[-*]\s+', line) or re.match(r'^\d+\.\s+', line):
            flush_para(para)
            ordered = bool(re.match(r'^\d+\.\s+', line))
            items: List[str] = []
            while i < n and (re.match(r'^[-*]\s+', lines[i]) or re.match(r'^\d+\.\s+', lines[i])):
                items.append(re.sub(r'^([-*]|\d+\.)\s+', '', lines[i].strip()))
                i += 1
            tag = "ol" if ordered else "ul"
            lis = "".join(f"<li>{_inline(x)}</li>" for x in items)
            out.append(f'<{tag} class="wp-block-list">{lis}</{tag}>')
            continue

        # --- table ---
        if line.startswith("|"):
            flush_para(para)
            rows: List[str] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip()); i += 1
            cells = [ [c.strip() for c in r.strip("|").split("|")] for r in rows ]
            cells = [r for r in cells if not all(re.fullmatch(r'[-: ]*', c or '') for c in r)]
            if cells:
                thead = "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells[0]) + "</tr>"
                tbody = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
                out.append(f'<figure class="wp-block-table"><table class="has-fixed-layout">{thead}{tbody}</table></figure>')
            continue

        # --- blank line ---
        if not line.strip():
            flush_para(para)
            i += 1; continue

        # --- paragraph accumulation ---
        para.append(line.strip())
        i += 1

    flush_para(para)
    return "\n\n".join(out), images, headings


def build_ez_toc(headings: List[Tuple[int, str]], include_h3: bool = False) -> str:
    """Generate Easy-TOC markup. By default only H2 entries are listed (H3 would overflow the TOC)."""
    if not headings:
        return ""
    items = []
    counter = 0
    for level, text in headings:
        if level >= 3 and not include_h3:
            continue  # skip H3+ in the visible TOC
        counter += 1
        anchor = slugify_anchor(text)
        cls = f"ez-toc-heading-level-{level}"
        items.append(
            f'<li class="ez-toc-page-1 {cls}"><a class="ez-toc-link ez-toc-heading-{counter}" href="#{anchor}">{text}</a></li>'
        )
    return (
        '<div id="ez-toc-container" class="ez-toc-v2_0_81 counter-hierarchy ez-toc-counter ez-toc-grey ez-toc-container-direction">\n'
        '<div class="ez-toc-title-container"><p class="ez-toc-title" style="cursor:inherit">Table of Contents</p></div>\n'
        '<nav><ul class="ez-toc-list ez-toc-list-level-1 ">' + "".join(items) + '</ul></nav></div>'
    )
