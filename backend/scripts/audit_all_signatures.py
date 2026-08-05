"""
Audit ALL users' signatures (user_signatures + legacy users.signature).
Flags rows containing HTML (<br>, <span>, <div>, <img>, <a>), HTML entities,
SIG markers, etc. so we know what needs cleaning.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

from app.database import get_db_connection
import psycopg2.extras


def flags_for(content):
    c = content or ""
    flags = []
    br = len(re.findall(r"<br\s*/?>", c, re.I))
    span = c.lower().count("<span")
    div = c.lower().count("<div")
    img = len(re.findall(r"<img\b", c, re.I))
    a_tag = len(re.findall(r"<a\b", c, re.I))
    strong = len(re.findall(r"<strong\b|<b\b", c, re.I))
    nbsp = c.count("&nbsp;") + c.count("\u00a0")
    has_entity = ("&amp;" in c) or ("&lt;" in c) or ("&gt;" in c)
    sigmark = "SIG_START" in c or "SIG_END" in c
    if br:
        flags.append(f"br={br}")
    if span:
        flags.append(f"span={span}")
    if div:
        flags.append(f"div={div}")
    if img:
        flags.append(f"img={img}")
    if a_tag:
        flags.append(f"a={a_tag}")
    if strong:
        flags.append(f"strong={strong}")
    if nbsp:
        flags.append(f"nbsp={nbsp}")
    if has_entity:
        flags.append("entity")
    if sigmark:
        flags.append("SIGMARK")
    return flags


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── user_signatures table ──
    cur.execute(
        """
        SELECT s.id, s.user_id, u.username, u.full_name, s.name, s.is_default, s.sig_type, s.content
        FROM user_signatures s LEFT JOIN users u ON s.user_id = u.id
        ORDER BY s.user_id, s.id
        """
    )
    rows = cur.fetchall()
    print(f"=== user_signatures ({len(rows)} rows) ===")
    for r in rows:
        flags = flags_for(r["content"])
        status = "CLEAN" if not flags else ", ".join(flags)
        print(f"  sig={r['id']} user={r['user_id']} ({r['username']}) type={r['sig_type']} default={r['is_default']} name={r['name']!r} => {status}")
        if flags:
            preview = (r["content"] or "")[:220].replace("\n", "\\n")
            print(f"      {preview!r}")

    # ── legacy users.signature column ──
    cur.execute("SELECT id, username, full_name, signature FROM users WHERE signature IS NOT NULL AND signature != ''")
    rows = cur.fetchall()
    print(f"\n=== legacy users.signature ({len(rows)} rows) ===")
    for r in rows:
        flags = flags_for(r["signature"])
        status = "CLEAN" if not flags else ", ".join(flags)
        print(f"  user={r['id']} ({r['username']}) => {status}")
        if flags:
            preview = (r["signature"] or "")[:220].replace("\n", "\\n")
            print(f"      {preview!r}")

    conn.close()


if __name__ == "__main__":
    main()
