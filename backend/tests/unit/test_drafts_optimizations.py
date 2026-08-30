"""Tests for drafts.py optimizations — table line-height, no markdown_to_html in loop."""
import re
import pytest
from unittest.mock import patch, MagicMock


class _FakeCursor:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, *a, **k): pass
    def fetchone(self): return None
    def fetchall(self): return []
    def close(self): pass
    rowcount = 0


class _FakeConn:
    def cursor(self, *a, **k): return _FakeCursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Prevent drafts.py from hitting real DB on import."""
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: _FakeConn())


def _md_to_html(text, **kwargs):
    """Call markdown_to_html without re-importing the module (avoids DB hits)."""
    import app.api.drafts as drafts_mod
    return drafts_mod.markdown_to_html(text, **kwargs)


class TestMarkdownToHtmlTableLineHeight:
    """markdown_to_html must set line-height:1.2 on table elements to prevent
    excessive spacing caused by the outer wrapper's line-height:1.6."""

    def test_table_has_line_height_12(self):
        md = "| Name | Age |\n|------|-----|\n| John | 30 |"
        html = _md_to_html(md)
        assert "line-height: 1.2" in html or "line-height:1.2" in html, f"table missing line-height:1.2 in:\n{html[:500]}"

    def test_th_has_line_height_12(self):
        md = "| Name | Age |\n|------|-----|\n| John | 30 |"
        html = _md_to_html(md)
        th_match = re.search(r"<th[^>]*style='([^']*)'", html)
        assert th_match, "no <th> found"
        assert "line-height: 1.2" in th_match.group(1) or "line-height:1.2" in th_match.group(1), f"<th> missing line-height:1.2: {th_match.group(1)}"

    def test_td_has_line_height_12(self):
        md = "| Name | Age |\n|------|-----|\n| John | 30 |"
        html = _md_to_html(md)
        td_match = re.search(r"<td[^>]*style='([^']*)'", html)
        assert td_match, "no <td> found"
        assert "line-height: 1.2" in td_match.group(1) or "line-height:1.2" in td_match.group(1), f"<td> missing line-height:1.2: {td_match.group(1)}"

    def test_non_table_paragraphs_unaffected(self):
        """Paragraphs should NOT get line-height:1.2."""
        md = "Hello world"
        html = _md_to_html(md)
        # Paragraphs use 1.4 (non-gmail) or 1.5 (gmail style), not 1.2
        assert "line-height: 1.4" in html or "line-height:1.4" in html or "line-height: 1.5" in html or "line-height:1.5" in html
        assert "line-height: 1.2" not in html and "line-height:1.2" not in html

    def test_table_preserves_content(self):
        md = "| Col1 | Col2 |\n|------|------|\n| A | B |\n| C | D |"
        html = _md_to_html(md)
        assert "Col1" in html
        assert "Col2" in html
        assert ">A<" in html
        assert ">D<" in html

    def test_empty_table(self):
        md = ""
        html = _md_to_html(md)
        assert "<table" not in html

    def test_sig_markers_stripped(self):
        md = "SIG_START\nHello\nSIG_END\n\nWorld"
        html = _md_to_html(md)
        assert "SIG_START" not in html
        assert "SIG_END" not in html
        assert "World" in html

    def test_sig_markers_with_text_outside(self):
        md = "Before SIG_START secret SIG_END After"
        html = _md_to_html(md)
        assert "Before" in html
        assert "After" in html
        assert "SIG_START" not in html
        assert "secret" not in html
