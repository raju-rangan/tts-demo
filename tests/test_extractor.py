"""Unit tests for Web Article Main Content Extractor."""
import pytest
from unittest.mock import patch, MagicMock
import httpx

from src.utils.extractor import (
    validate_url,
    extract_article_from_html,
    extract_article_from_url,
    ExtractedArticle
)


def test_validate_url():
    """Verify URL validation for valid and invalid formats."""
    assert validate_url("https://www.federalreserve.gov/newsevents/pressreleases/monetary20260918a.htm") is True
    assert validate_url("http://example.com/banking/article") is True
    assert validate_url("https://sub.domain.co.uk/path?param=1#anchor") is True

    assert validate_url("not_a_url") is False
    assert validate_url("ftp://example.com/file.txt") is False
    assert validate_url("http://") is False
    assert validate_url("https://nodotdomain") is False
    assert validate_url("") is False
    assert validate_url(None) is False


def test_extract_article_from_html_semantic():
    """Verify main content parser extracts article body and ignores headers, navs, and footers."""
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Commercial Real Estate Liquidity Guidelines | Banking Review</title>
        <meta property="og:title" content="Commercial Real Estate Liquidity Guidelines">
    </head>
    <body>
        <nav>
            <ul><li><a href="/home">Home</a></li><li><a href="/login">Customer Portal</a></li></ul>
        </nav>
        <header>
            <div class="logo">Apex Financial Logo</div>
            <span>Menu Toggle</span>
        </header>

        <main>
            <article class="article-body">
                <h1>Commercial Real Estate Liquidity Guidelines</h1>
                <p>Commercial real estate (CRE) lending requires disciplined stress testing and comprehensive debt service coverage evaluations across regional portfolios.</p>
                <p>Financial institutions should maintain adequate Tier 1 capital buffers to absorb potential valuation fluctuations in metropolitan commercial properties.</p>
                <p>The Federal Reserve and Office of the Comptroller of the Currency (OCC) emphasize active loan-to-value monitoring and debt yield covenants for multifamily assets.</p>
            </article>
        </main>

        <aside class="sidebar">
            <h3>Trending Stories</h3>
            <p>Subscribe to our newsletter for morning market alerts.</p>
        </aside>

        <footer>
            <p>Copyright 2026 Apex Financial Group. All rights reserved. Privacy Policy | Terms of Use.</p>
        </footer>
    </body>
    </html>
    """

    article = extract_article_from_html(sample_html, source_url="https://apexbank.com/cre-guidelines")
    assert isinstance(article, ExtractedArticle)
    assert article.title == "Commercial Real Estate Liquidity Guidelines"
    assert "Commercial real estate (CRE) lending requires" in article.text
    assert "Office of the Comptroller of the Currency" in article.text
    assert "Customer Portal" not in article.text
    assert "All rights reserved" not in article.text
    assert article.word_count > 30
    assert article.url == "https://apexbank.com/cre-guidelines"


def test_extract_article_from_html_fallback():
    """Verify parser falls back to body paragraphs when no article tag is present."""
    html_without_article = """
    <html>
    <head><title>Retail Deposit Yields Update</title></head>
    <body>
        <p>Annual percentage yields on short-term deposits have stabilized following recent central bank announcements.</p>
        <p>Treasury bills and high-yield money market products continue to attract substantial inflows from risk-conscious retail depositors.</p>
        <p>Portfolio managers recommend maintaining laddered maturity horizons to mitigate ongoing reinvestment rate uncertainties.</p>
    </body>
    </html>
    """
    article = extract_article_from_html(html_without_article, source_url="https://example.com/yields")
    assert article.title == "Retail Deposit Yields Update"
    assert "Annual percentage yields" in article.text
    assert "Portfolio managers recommend" in article.text
    assert article.word_count >= 25


def test_extract_article_from_html_too_short():
    """Verify that thin or empty pages raise a ValueError."""
    empty_html = """<html><body><p>Under maintenance.</p></body></html>"""
    with pytest.raises(ValueError, match="too short"):
        extract_article_from_html(empty_html, source_url="https://example.com/short")


def test_extract_article_from_url_success():
    """Verify extract_article_from_url calls httpx and parses response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <html>
    <head><title>Mortgage Lending Strategies 2026</title></head>
    <body>
        <main>
            <p>Fixed-rate mortgages remain the preferred financing choice for first-time residential homebuyers seeking payment predictability.</p>
            <p>Underwriting standards continue to evaluate debt-to-income ratios alongside secondary liquidity reserves to ensure sustainable homeownership.</p>
        </main>
    </body>
    </html>
    """

    with patch("httpx.Client.get", return_value=mock_resp):
        article = extract_article_from_url("https://apexbank.com/mortgage-strategies")
        assert article.title == "Mortgage Lending Strategies 2026"
        assert "Fixed-rate mortgages" in article.text
        assert article.word_count >= 25


def test_extract_article_from_url_http_error():
    """Verify HTTP errors raise RuntimeError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.reason_phrase = "Not Found"

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="HTTP 404"):
            extract_article_from_url("https://apexbank.com/nonexistent-article")


def test_extract_article_from_url_timeout():
    """Verify timeout errors raise TimeoutError."""
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(TimeoutError, match="timed out"):
            extract_article_from_url("https://apexbank.com/slow-article")
