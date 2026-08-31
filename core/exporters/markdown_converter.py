"""Shared Markdown to HTML converter used by PDF export and blog export."""
from __future__ import annotations
import re


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80].strip('-')


def markdown_to_html(md_text: str, include_images: bool = True) -> str:
    html = md_text

    # Headers
    html = re.sub(r'^#### (.*$)', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*$)', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*$)', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*$)', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)

    # Bold / italic
    html = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Images (optional; skipped in PDF)
    if include_images:
        html = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)',
                      r'<img src="\2" alt="\1">', html)
    else:
        html = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'<p><em>[Image: \1]</em></p>', html)

    # Blockquotes (multi-line aware)
    html = re.sub(r'(^> .*(?:\n> .*)*)', _blockquote, html, flags=re.MULTILINE)

    # Tables
    html = re.sub(r'((?:^\|.*\|\n)+)', _table, html, flags=re.MULTILINE)

    # Unordered lists
    html = re.sub(r'((?:^[-*] .*\n?)+)', _ul, html, flags=re.MULTILINE)
    # Ordered lists
    html = re.sub(r'((?:^\d+\. .*\n?)+)', _ol, html, flags=re.MULTILINE)

    # Paragraphs: wrap loose lines
    out = []
    for block in re.split(r'\n\n+', html):
        block = block.strip()
        if not block:
            continue
        if block.startswith(('<h', '<ul', '<ol', '<table', '<blockquote', '<hr', '<img', '<p')):
            out.append(block)
        elif '\n' in block and not block.startswith('<'):
            # multi-line plain text -> join into one paragraph
            out.append('<p>' + block.replace('\n', ' ') + '</p>')
        else:
            out.append('<p>' + block + '</p>')
    return '\n'.join(out)


def _blockquote(m: re.Match) -> str:
    inner = re.sub(r'^> ?', '', m.group(1), flags=re.MULTILINE)
    return '<blockquote>' + inner.replace('\n', '<br>') + '</blockquote>'


def _table(m: re.Match) -> str:
    rows = [r.strip() for r in m.group(1).strip().split('\n')]
    html_rows = ['<table>']
    for i, row in enumerate(rows):
        if re.match(r'^\|[\s\-:|]+\|$', row):
            continue
        cells = [c.strip() for c in row.strip('|').split('|')]
        tag = 'th' if i == 0 else 'td'
        html_rows.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
    html_rows.append('</table>')
    return '\n'.join(html_rows)


def _ul(m: re.Match) -> str:
    items = re.findall(r'^[-*] (.*)$', m.group(1), flags=re.MULTILINE)
    return '<ul>' + ''.join(f'<li>{i}</li>' for i in items) + '</ul>'


def _ol(m: re.Match) -> str:
    items = re.findall(r'^\d+\. (.*)$', m.group(1), flags=re.MULTILINE)
    return '<ol>' + ''.join(f'<li>{i}</li>' for i in items) + '</ol>'
