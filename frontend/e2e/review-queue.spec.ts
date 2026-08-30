"""E2E smoke tests — review queue loads without JS errors."""
import re
from playwright.sync_api import Page, expect


def test_review_queue_loads_no_js_errors(page: Page):
    """Navigate to review queue, verify page loads and no console errors."""
    errors: list[str] = []

    def on_console(msg):
        if msg.type == "error":
            errors.append(msg.text)

    page.on("console", on_console)
    page.goto("/dashboard/emails")

    # Wait for page to render
    page.wait_for_load_state("networkidle")

    # Verify no fatal JS errors (filter out known non-critical warnings)
    fatal = [e for e in errors if "TypeError" in e or "ReferenceError" in e or "SyntaxError" in e]
    assert not fatal, f"JS errors on review queue page:\n" + "\n".join(fatal)


def test_review_queue_has_content(page: Page):
    """Review queue page should have some visible content after load."""
    page.goto("/dashboard/emails")
    page.wait_for_load_state("networkidle")

    # Page should not be blank
    body_text = page.inner_text("body")
    assert len(body_text.strip()) > 0, "Review queue page is blank"
