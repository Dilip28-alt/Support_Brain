import pytest
from app.utils.html_utils import clean_html_to_text, extract_readable_email_text, is_html_content


def test_is_html_content():
    assert is_html_content("<p>Hello</p>") is True
    assert is_html_content("Hello <b>world</b>") is True
    assert is_html_content("<div>Content</div>") is True
    assert is_html_content("Just plain text with no tags") is False
    assert is_html_content("Price: $50 < $100") is False  # Not an HTML tag


def test_clean_html_strips_scripts_and_styles():
    raw = """
    <html>
      <head>
        <style>body { background-color: red; }</style>
        <script>alert('malicious script');</script>
      </head>
      <body>
        <h1>Order Confirmation</h1>
        <p>Thank you for your order! Your item has shipped.</p>
        <script>document.location='http://evil.com';</script>
      </body>
    </html>
    """
    cleaned = clean_html_to_text(raw)
    assert "alert" not in cleaned
    assert "background-color" not in cleaned
    assert "Order Confirmation" in cleaned
    assert "Thank you for your order! Your item has shipped." in cleaned
    assert "<" not in cleaned and ">" not in cleaned


def test_clean_html_unescapes_entities():
    raw = "<p>Tom &amp; Jerry &bull; Price: &pound;25 &nbsp; &copy; 2026</p>"
    cleaned = clean_html_to_text(raw)
    assert "Tom & Jerry" in cleaned
    assert "£25" in cleaned
    assert "© 2026" in cleaned


def test_extract_readable_email_text_prefers_clean_plain_text():
    plain = "Hello, I want to know about your warranty terms."
    html_part = "<p>Hello, I want to know about your <b>warranty</b> terms.</p>"
    result = extract_readable_email_text(body_text=plain, body_html=html_part)
    assert result == plain


def test_extract_readable_email_text_converts_html_when_plain_empty():
    html_part = "<div><h3>Product Inquiry</h3><p>What is the price of laptop BCD-LP101?</p></div>"
    result = extract_readable_email_text(body_text="", body_html=html_part)
    assert "Product Inquiry" in result
    assert "What is the price of laptop BCD-LP101?" in result
    assert "<" not in result and ">" not in result


def test_extract_readable_email_text_cleans_html_inside_body_text():
    raw_in_body_text = "<html><body><p>Direct inquiry without multipart.</p></body></html>"
    result = extract_readable_email_text(body_text=raw_in_body_text, body_html=None)
    assert result == "Direct inquiry without multipart."
    assert "<" not in result and ">" not in result
