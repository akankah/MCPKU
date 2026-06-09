import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from web.parsers import html_to_text as _html_to_text


class TestHtmlToText:
    def test_strips_tags(self):
        assert "hello world" in _html_to_text("<html><body><p>hello world</p></body></html>")

    def test_extracts_links(self):
        result = _html_to_text('<a href="https://example.com">click here</a>')
        assert "click here" in result

    def test_empty_html(self):
        assert _html_to_text("") == ""

    def test_plain_text(self):
        assert _html_to_text("just text") == "just text"

    def test_line_breaks(self):
        result = _html_to_text("<p>line1</p><p>line2</p>")
        assert "line1" in result
        assert "line2" in result
