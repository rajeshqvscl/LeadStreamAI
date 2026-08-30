"""Tests for image dimension propagation in markdown_to_html."""
import pytest
from unittest.mock import patch


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
    import app.database as dbmod
    monkeypatch.setattr(dbmod, "get_db_connection", lambda *a, **k: _FakeConn())


def _md_to_html(text, **kwargs):
    import app.api.drafts as drafts_mod
    return drafts_mod.markdown_to_html(text, **kwargs)


# A small 1x1 red PNG encoded as base64
_TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
_DATA_URI = f"data:image/png;base64,{_TINY_PNG_B64}"


class TestImageDimensionDefaults:

    def test_data_uri_uses_custom_width(self):
        html = _md_to_html(f"![alt]({_DATA_URI})", image_width="200px", image_height="150px")
        assert "200px" in html, f"Expected 200px in: {html}"
        assert "150px" in html

    def test_data_uri_default_width(self):
        html = _md_to_html(f"![alt]({_DATA_URI})", image_width="400px", image_height="auto")
        assert "400px" in html
        assert "auto" in html

    def test_external_image_responsive(self):
        """External images use width:100% regardless of image_width param."""
        html = _md_to_html("![alt](http://img.png)", image_width="200px", image_height="150px")
        assert "width:100%" in html

    def test_no_image_tag_unchanged(self):
        html = _md_to_html("Hello world", image_width="100px", image_height="50px")
        assert "100px" not in html
        assert "50px" not in html
