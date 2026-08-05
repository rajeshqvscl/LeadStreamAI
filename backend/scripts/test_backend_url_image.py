"""
Verify the reviewer-flagged regression fix: markdown-path images using the
[[BACKEND_URL]] placeholder (as produced by clean_signature_markdown) must
render with the real backend URL, matching the rich-HTML path behaviour.
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

DIRTY = ('--&nbsp;<div style="color: rgb(0, 0, 0);">Thanks &amp; Regards,<br>'
         '<strong>Kajal Narang</strong><br>Deputy Manager<br>'
         '<a href="https://qvscl.com">Website</a></div>'
         '<img src="[[BACKEND_URL]]/assets/kajal.png" style="width: 150px;" />')

backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def main():
    cleaned = clean_signature_markdown(DIRTY)
    print("cleaned img line:", [ln for ln in cleaned.split("\n") if "kajal.png" in ln])

    html = markdown_to_html(cleaned)
    expected = f'src="{backend_url}/assets/kajal.png"'
    print("rendered img tag:")
    for seg in html.split("<img"):
        if "kajal.png" in seg:
            print("  <img" + seg[:120])
    print("placeholder resolved:", "[[BACKEND_URL]]" not in html)
    print("real url present:", expected in html)

    ok = ("[[BACKEND_URL]]" not in html) and (expected in html)
    print("\nRESULT:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
