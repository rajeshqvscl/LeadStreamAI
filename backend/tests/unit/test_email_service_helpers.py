"""
Unit tests for email_service helper functions (clean_display_filename).
Pure logic — no DB, no network.
"""

import pytest

from app.services.email_service import clean_display_filename


class TestCleanDisplayFilename:
    """Strip internal sig_ prefixes from filenames."""

    def test_sig_userid_prefix(self):
        assert clean_display_filename("sig_5_QVSCL_Company_Profile.pdf") == "QVSCL_Company_Profile.pdf"

    def test_sig_userid_numeric(self):
        assert clean_display_filename("sig_123_my_report.xlsx") == "my_report.xlsx"

    def test_sig_att_legacy_prefix(self):
        assert clean_display_filename("sig_att_old_file.pdf") == "old_file.pdf"

    def test_normal_filename_unchanged(self):
        assert clean_display_filename("normal.pdf") == "normal.pdf"

    def test_none_input(self):
        assert clean_display_filename(None) is None

    def test_empty_string(self):
        assert clean_display_filename("") == ""

    def test_path_separators_stripped(self):
        assert clean_display_filename("uploads/sig_5_test.pdf") == "test.pdf"

    def test_sig_userid_large_id(self):
        assert clean_display_filename("sig_99999_document.docx") == "document.docx"

    def test_sig_att_with_path(self):
        assert clean_display_filename("files/sig_att_report.pdf") == "report.pdf"

    def test_no_prefix_with_path(self):
        assert clean_display_filename("uploads/regular.pdf") == "regular.pdf"

    def test_sig_userid_case_insensitive(self):
        assert clean_display_filename("SIG_5_file.pdf") == "file.pdf"

    def test_sig_att_case_insensitive(self):
        assert clean_display_filename("SIG_ATT_file.pdf") == "file.pdf"
