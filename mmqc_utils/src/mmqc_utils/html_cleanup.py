"""Post-process converted HTML: remove pandoc structural artifacts."""

from __future__ import annotations

import re
from collections.abc import Callable

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import PageElement, PreformattedString

_BR_ONLY = re.compile(r"(<br\s*/?>|\s)+", re.I)


def visible_text(tag: Tag) -> str:
    """Return the whitespace-normalized visible text of a tag."""
    parts: list[str] = []
    for child in tag.descendants:
        if isinstance(child, NavigableString):
            parts.append(str(child))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def is_br_only(tag: Tag) -> bool:
    """Return True if a tag contains only ``<br/>`` elements and whitespace."""
    inner = (tag.decode_contents() or "").strip()
    return bool(inner) and bool(_BR_ONLY.fullmatch(inner))


def is_empty_tag(tag: Tag) -> bool:
    """Return True if a tag has no visible text and no br-only content."""
    return not visible_text(tag) and not is_br_only(tag)


def remove_br_only_elements(soup: BeautifulSoup) -> int:
    """Strip tags that contain only ``<br/>`` layout placeholders."""
    removed = 0
    for tag in list(soup.find_all(["p", "div", "span", "strong", "em"])):
        if is_br_only(tag):
            tag.decompose()
            removed += 1
    return removed


def remove_empty_elements(soup: BeautifulSoup) -> int:
    """Remove empty ``<p>``, ``<div>``, ``<span>`` and ``<a>`` tags.

    ``<td>``/``<th>`` are intentionally not removed to preserve table
    column structure.
    """
    removed = 0
    for tag in list(soup.find_all(["p", "div", "span", "a"])):
        if is_empty_tag(tag):
            tag.decompose()
            removed += 1
    return removed


def unwrap_li_paragraphs(soup: BeautifulSoup) -> int:
    """Unwrap ``<li><p>…</p></li>`` to ``<li>…</li>``."""
    count = 0
    for li in soup.find_all("li"):
        children = [c for c in li.children if isinstance(c, Tag)]
        direct_ps = [c for c in children if c.name == "p"]
        if len(direct_ps) == 1 and len(children) == 1:
            direct_ps[0].unwrap()
            count += 1
    return count


def _paragraph_urls(p: Tag) -> list[str]:
    urls: list[str] = []
    for a in p.find_all("a", href=True):
        href_attr = a.get("href")
        href = href_attr.strip() if isinstance(href_attr, str) else ""
        text = visible_text(a)
        if href:
            urls.append(href)
        if text and text.startswith("http"):
            urls.append(text)
    text = visible_text(p)
    if text.startswith("http") and len(text.split()) == 1:
        urls.append(text)
    return urls


def _recent_text(blocks: list[Tag], idx: int, lookback: int = 3) -> str:
    chunks: list[str] = []
    for block in blocks[max(0, idx - lookback) : idx]:
        chunks.append(visible_text(block))
    return " ".join(chunks)


def remove_orphan_url_paragraphs(soup: BeautifulSoup) -> int:
    """Remove orphan URL ``<p>`` blocks when the URL already appears nearby."""
    blocks = [el for el in soup.children if isinstance(el, Tag)]
    removed = 0
    for idx, block in enumerate(blocks):
        if block.name != "p":
            continue
        urls = _paragraph_urls(block)
        if not urls:
            continue
        context = _recent_text(blocks, idx)
        if all(url in context for url in urls):
            block.decompose()
            removed += 1
    return removed


_POSTPROCESS_STEPS: tuple[Callable[[BeautifulSoup], int], ...] = (
    remove_br_only_elements,
    remove_empty_elements,
    unwrap_li_paragraphs,
    remove_orphan_url_paragraphs,
)


def _serialize(node: PageElement) -> str:
    """Return the markup of a top-level node.

    ``str()`` drops the delimiters of a doctype or comment: ``str(Doctype)`` is
    ``"html"``, not ``"<!DOCTYPE html>"``.
    """
    if isinstance(node, PreformattedString):
        return node.output_ready()
    return str(node)


def postprocess_html(html: str) -> str:
    """Run all HTML cleanup steps and return cleaned markup."""
    soup = BeautifulSoup(html or "", "html.parser")
    for step in _POSTPROCESS_STEPS:
        step(soup)
    return "".join(_serialize(child) for child in soup.children if str(child).strip())
