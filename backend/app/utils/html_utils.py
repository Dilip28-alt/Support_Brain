"""
HTML to readable plain-text extraction and sanitization utilities.
Ensures email content displayed in Support Brain is human-readable,
free of raw HTML tags, and completely safe from malicious scripts/content.
"""
import re
import html
import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z/][^>]*>")


def is_html_content(text: Optional[str]) -> bool:
    """Check if a string appears to contain HTML markup."""
    if not text or not isinstance(text, str):
        return False
    return bool(HTML_TAG_PATTERN.search(text))


def clean_html_to_text(raw_html: Optional[str]) -> str:
    """
    Safely converts HTML markup to clean, readable plain text.
    - Strips script, style, head, meta, link, noscript tags and their contents.
    - Converts break, paragraph, div, and list tags to natural linebreaks.
    - Decodes all HTML entities (&nbsp;, &amp;, &lt;, etc.).
    - Collapses redundant whitespace while preserving paragraph structure.
    - Never executes or exposes scripts or malicious content.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""

    if not is_html_content(raw_html):
        return raw_html.strip()

    try:
        soup = BeautifulSoup(raw_html, "html.parser")

        # Strip all unsafe or non-content tags completely
        for tag in soup(["script", "style", "head", "meta", "title", "noscript", "link", "svg", "iframe", "object", "embed"]):
            tag.decompose()

        # Insert newlines after block elements and breaks to preserve readable layout
        for block_tag in soup.find_all(["br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "blockquote"]):
            block_tag.insert_after("\n")

        text = soup.get_text()
        text = html.unescape(text)

        # Normalize whitespace and excessive newlines
        lines = [line.strip() for line in text.splitlines()]
        # Collapse multiple blank lines into at most one empty line
        cleaned_lines = []
        last_blank = False
        for line in lines:
            if line:
                cleaned_lines.append(line)
                last_blank = False
            elif not last_blank:
                cleaned_lines.append("")
                last_blank = True

        return "\n".join(cleaned_lines).strip()
    except Exception as e:
        logger.warning(f"Error parsing HTML with BeautifulSoup, using regex fallback: {e}")
        # Robust fallback using regex if parser fails
        clean = re.sub(r"<(script|style|head|title)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<(br|p|div|tr|li|h[1-6])[^>]*>", "\n", clean, flags=re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = html.unescape(clean)
        lines = [l.strip() for l in clean.splitlines() if l.strip()]
        return "\n".join(lines).strip()


def extract_readable_email_text(
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """
    Given text/plain and text/html MIME parts from an incoming email:
    1. If body_text exists and does not contain raw HTML tags, return it.
    2. If body_text contains raw HTML or is empty, use body_html (or body_text)
       and convert it to clean, readable plain text.
    3. If both are empty, fall back to the subject or empty string.
    """
    # 1. If clean plain text is available and not raw HTML, use it
    if body_text and body_text.strip():
        stripped = body_text.strip()
        if not is_html_content(stripped):
            return stripped
        # body_text itself contained HTML tags
        cleaned = clean_html_to_text(stripped)
        if cleaned:
            return cleaned

    # 2. If body_html is available, convert it to readable text
    if body_html and body_html.strip():
        cleaned = clean_html_to_text(body_html)
        if cleaned:
            return cleaned

    # 3. Fallback to subject
    if subject and subject.strip():
        return subject.strip()

    return ""
