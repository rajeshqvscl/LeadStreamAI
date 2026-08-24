"""
Round-trip test: WYSIWYG HTML (as the editor would send) -> clean markdown
-> rendered HTML. Verifies the permanent save-time cleanup produces a clean
email without <br>/rgb-spans/&nbsp; while preserving links/bold/images.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.utils.signature_clean import clean_signature_markdown
from app.api.drafts import markdown_to_html

DIRTY_HTML = """--&nbsp;<div style="color: rgb(0, 0, 0); font-family: sans-serif;">Thanks &amp; Regards,<br><strong>Kajal Narang</strong><br>Deputy Manager<br><a href="https://qvscl.com">Website</a> | <a href="https://www.linkedin.com/company/qvscl/">LinkedIn</a><br>+91 7982721309</div><img src="[[BACKEND_URL]]/assets/kajal.png" style="width: 150px;" />"""


def main():
    cleaned = clean_signature_markdown(DIRTY_HTML)
    print("=== cleaned markdown ===")
    for ln in cleaned.split("\n"):
        print("  %r" % ln)

    html = markdown_to_html(cleaned)
    print("\n=== rendered HTML checks ===")
    print("  <br> count:", html.count("<br"))
    # NOTE: markdown_to_html wraps the signature block in its own styling spans
    # (color:#666) — that is expected. The DIRTY rgb(0,0,0) WYSIWYG span is what
    # must be gone.
    print("  dirty rgb span present:", "color: rgb" in html)
    print("  &nbsp; present:", "&nbsp;" in html)
    print("  link preserved:", 'href="https://qvscl.com"' in html)
    print("  linkedin preserved:", 'href="https://www.linkedin.com/company/qvscl/"' in html)
    print("  bold preserved:", "<strong>Kajal Narang</strong>" in html)
    print("  img preserved:", "<img" in html and "kajal.png" in html)

    # Idempotency: running again on the clean markdown must not change it
    cleaned2 = clean_signature_markdown(cleaned)
    print("\n  idempotent:", cleaned2 == cleaned)

    ok = (
        "<br" not in html
        and "color: rgb" not in html
        and "&nbsp;" not in html
        and 'href="https://qvscl.com"' in html
        and "<strong>Kajal Narang</strong>" in html
        and cleaned2 == cleaned
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
