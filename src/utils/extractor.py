"""Web Article Main Content Extractor using standard library HTMLParser and httpx."""
import re
from html.parser import HTMLParser
from typing import List, Optional, Tuple
import logging
from urllib.parse import urlparse
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedArticle(BaseModel):
    """Structured representation of extracted web article content."""
    url: str = Field(..., description="Source URL of the article")
    title: str = Field(..., description="Cleaned article title")
    text: str = Field(..., description="Main readable article text")
    word_count: int = Field(..., description="Total word count of extracted text")
    char_count: int = Field(..., description="Total character count of extracted text")


class MainContentHTMLParser(HTMLParser):
    """Robust HTML parser that extracts title, main body text, and removes non-content elements."""

    IGNORE_TAGS = {
        "script", "style", "noscript", "header", "footer", "nav",
        "aside", "form", "svg", "button", "select", "option",
        "menu", "dialog", "iframe"
    }

    BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"}

    def __init__(self):
        super().__init__()
        self.ignore_depth = 0
        self.in_head = False
        self.in_title = False
        self.raw_title = ""
        self.meta_og_title = ""
        self.meta_twitter_title = ""
        
        # Article / Main content tracking
        self.article_depth = 0
        self.main_paragraphs: List[str] = []
        self.fallback_paragraphs: List[str] = []
        self.current_buffer: List[str] = []
        self.current_tag: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs}
        tag_lower = tag.lower()

        if tag_lower == "head":
            self.in_head = True
            return

        # Metadata titles
        if tag_lower == "meta":
            prop = attr_dict.get("property", "").lower()
            name = attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "").strip()
            if prop == "og:title" and content:
                self.meta_og_title = content
            elif name == "twitter:title" and content:
                self.meta_twitter_title = content

        if tag_lower in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return

        if self.ignore_depth > 0:
            return

        if tag_lower == "title":
            self.in_title = True
            return

        # Check for semantic main/article containers
        role = attr_dict.get("role", "").lower()
        cls = attr_dict.get("class", "").lower()
        elem_id = attr_dict.get("id", "").lower()
        is_article_elem = (
            tag_lower in {"article", "main"} or
            role == "main" or
            any(k in cls or k in elem_id for k in ["article-body", "post-content", "entry-content", "main-content", "article__body"])
        )
        if is_article_elem:
            self.article_depth += 1

        if tag_lower in self.BLOCK_TAGS:
            self._flush_current_buffer()
            self.current_tag = tag_lower

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        if tag_lower == "head":
            self.in_head = False
            return

        if tag_lower in self.IGNORE_TAGS and self.ignore_depth > 0:
            self.ignore_depth -= 1
            return

        if self.ignore_depth > 0:
            return

        if tag_lower == "title":
            self.in_title = False
            return

        if tag_lower in {"article", "main"} and self.article_depth > 0:
            self.article_depth -= 1

        if tag_lower in self.BLOCK_TAGS:
            self._flush_current_buffer()
            self.current_tag = None

    def handle_data(self, data: str):
        if self.ignore_depth > 0:
            return

        if self.in_title:
            self.raw_title += data
            return

        if self.in_head:
            return

        clean = data.strip()
        if clean:
            self.current_buffer.append(data)

    def _flush_current_buffer(self):
        if not self.current_buffer:
            return
        raw_text = "".join(self.current_buffer)
        normalized = " ".join(raw_text.split())
        self.current_buffer = []

        if not normalized:
            return

        # Filter out common UI boilerplate fragments
        lower_text = normalized.lower()
        boilerplate_snippets = [
            "cookie policy", "terms of use", "privacy policy", "all rights reserved",
            "subscribe to our", "sign up for", "share on facebook", "share on twitter",
            "advertisement", "scroll to continue"
        ]
        if any(b in lower_text for b in boilerplate_snippets) and len(normalized.split()) < 15:
            return

        # Only capture text snippets with meaningful content (> 3 words or substantive text)
        if len(normalized.split()) >= 3:
            if self.article_depth > 0:
                self.main_paragraphs.append(normalized)
            else:
                self.fallback_paragraphs.append(normalized)

    def get_extracted_content(self, fallback_title: str = "Web Article") -> Tuple[str, str]:
        """Returns (title, full_text)."""
        self._flush_current_buffer()

        # Determine best title
        title = self.meta_og_title or self.meta_twitter_title or self.raw_title.strip() or fallback_title
        title = " ".join(title.split())
        # Clean title suffix (e.g. 'Article Title | Bloomberg')
        if "|" in title:
            title = title.split("|")[0].strip()
        elif " - " in title:
            title = title.split(" - ")[0].strip()

        # Determine paragraphs (prefer article container if substantial)
        paragraphs = self.main_paragraphs if len(self.main_paragraphs) >= 2 else self.fallback_paragraphs
        if not paragraphs and self.main_paragraphs:
            paragraphs = self.main_paragraphs

        # De-duplicate consecutive identical lines
        deduped: List[str] = []
        for p in paragraphs:
            if not deduped or p != deduped[-1]:
                deduped.append(p)

        full_text = "\n\n".join(deduped).strip()
        return title, full_text


def validate_url(url: str) -> bool:
    """Validates that a URL is well-formed with http or https scheme."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and "." in parsed.netloc


def extract_article_from_html(html: str, source_url: str = "") -> ExtractedArticle:
    """Synchronously parses HTML text and extracts clean main article content."""
    parser = MainContentHTMLParser()
    parser.feed(html)
    title, text = parser.get_extracted_content(fallback_title=source_url or "Web Article")

    # If title is in the text as the first heading, format nicely
    if title and not text.startswith(title):
        full_transcript = f"{title}\n\n{text}".strip()
    else:
        full_transcript = text.strip() or title

    words = len(full_transcript.split())
    chars = len(full_transcript)

    if words < 25:
        raise ValueError(
            f"Extracted content from '{source_url or 'HTML'}' is too short ({words} words). "
            "The page may be protected by a login, bot firewall, or require client-side JavaScript."
        )

    return ExtractedArticle(
        url=source_url,
        title=title or "Web Article",
        text=full_transcript,
        word_count=words,
        char_count=chars
    )


def extract_article_from_url(url: str, timeout: float = 15.0) -> ExtractedArticle:
    """Fetches a web page over HTTP/HTTPS and extracts clean readable article content."""
    clean_url = url.strip()
    if not validate_url(clean_url):
        raise ValueError(f"Invalid URL format: '{clean_url}'. Must start with http:// or https:// and include a valid domain.")

    headers = {
        "User-Agent": "ApexBankKnowledgeVoice/1.0 (support@apexbank.com) Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    logger.info(f"🌐 Fetching URL for extraction: {clean_url}")
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.get(clean_url)
            # If rejected with 403, retry once with standard direct bot identification
            if resp.status_code == 403:
                fallback_headers = {
                    "User-Agent": "ApexBankKnowledgeVoice/1.0 (support@apexbank.com)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                resp = client.get(clean_url, headers=fallback_headers)

            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code} ({resp.reason_phrase}) returned by server for {clean_url}")
            html_content = resp.text
    except httpx.TimeoutException:
        raise TimeoutError(f"Connection timed out after {timeout}s while fetching {clean_url}")
    except httpx.RequestError as e:
        raise RuntimeError(f"Network error accessing {clean_url}: {e}")

    return extract_article_from_html(html=html_content, source_url=clean_url)
