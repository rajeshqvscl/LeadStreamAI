"""
Shared signature cleanup: converts HTML/rich-text signature content (as emitted
by the frontend WYSIWYG editor — <div>, <span style=...>, <br>, &nbsp;, &amp;)
into clean plain markdown, matching the format of the hand-edited signatures
(Kajal / Yashika / Palak): markdown links, **bold**, no <br>, no HTML entities.

Idempotent: already-clean markdown passes through unchanged, so calling it on
every save is safe.

Applied at save time (create/update signature endpoints) so the <br>-laden HTML
format can never be stored again.
"""
import html as _html
import re

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
# Any real HTML tag at all (not the '--' separator, not markdown)
_HTML_TAG_RE = re.compile(r"<[a-zA-Z!/][^>]*>")


def _img_repl(m):
    attrs = m.group(0)
    src = re.search(r"""src\s*=\s*["']([^"']*)["']""", attrs)
    alt = re.search(r"""alt\s*=\s*["']([^"']*)["']""", attrs)
    url = src.group(1) if src else ""
    alt_text = alt.group(1) if alt else "image"
    return f"![{alt_text}]({url})"


def _a_repl(m):
    attrs = m.group(1)
    text = m.group(2)
    href = re.search(r"""href\s*=\s*["']([^"']*)["']""", attrs)
    url = href.group(1) if href else ""
    # Link text may still contain leftover tags (<br>, <b>, ...) or newlines
    # from nested HTML — strip them so the markdown link stays valid.
    text = _BR_RE.sub(" ", text)
    text = re.sub(r"<[^>]+>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return f"[{text}]({url})"


def clean_signature_markdown(text):
    """Convert HTML/rich-text signature content to clean plain markdown.

    - Decodes HTML entities (&amp; -> &, &nbsp; -> space, ...)
    - <br> -> newline
    - <a href="u">t</a> -> [t](u)   (links preserved)
    - <img src="u" alt="a"> -> ![a](u)
    - <strong>/<b> -> **text**
    - <em>/<i> -> *text* (markdown italic — supported by markdown_to_html and the editor)
    - <span style="color:/background-color:/font-..."> -> KEPT as inline HTML
      (colored / highlighted / styled signature text must survive saving; the
      markdown renderers pass raw inline HTML through)
    - <u>...</u> -> KEPT (underline is supported by the editor and renderer)
    - block tags (div/p/li/table/...) -> newlines
    - collapses blank lines; '--' separator kept on its own line
    """
    if not text:
        return text
    # Already clean markdown (no HTML tags) -> return unchanged.
    if not _HTML_TAG_RE.search(text):
        return text

    cleaned = _html.unescape(text)
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = _BR_RE.sub("\n", cleaned)

    # Images first (they contain <img ...> which the generic tag strip would eat)
    cleaned = re.sub(r"<img[^>]*>", _img_repl, cleaned, flags=re.IGNORECASE | re.DOTALL)
    # Links
    cleaned = re.sub(r"<a\s+([^>]*)>(.*?)</a>", _a_repl, cleaned, flags=re.IGNORECASE | re.DOTALL)
    # Bold
    cleaned = re.sub(r"</?(?:strong|b)>", "**", cleaned, flags=re.IGNORECASE)
    # Italic -> *text* markdown. markdown_to_html (its step-5 markdown pass) and
    # the frontend htmlToMd both support single-* italic, so keeping the markers
    # makes the editor preview and the rendered emails match what the user
    # saved (the signature format *Thanks & Regards,* already uses it).
    cleaned = re.sub(r"<em(?:\s[^>]*)?>|<i(?:\s[^>]*)?>", "*", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</em>|</i>", "*", cleaned, flags=re.IGNORECASE)
    # Block-level tags -> newline boundaries
    cleaned = re.sub(
        r"</?(?:div|p|h[1-6]|ul|ol|li|table|thead|tbody|tr|td|th|blockquote)[^>]*>",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Legacy <font color="..."> tags (older execCommand('foreColor') output in
    # some browsers) -> equivalent styled <span>, so their colors survive too.
    def _font_repl(m):
        attrs = m.group(1)
        styles = []
        # Value may be quoted ("#cc4125") or bare (red) — handle both.
        m_color = re.search(r"""color\s*=\s*(?:["']([^"']+)["']|([^\s>]+))""", attrs)
        m_face = re.search(r"""face\s*=\s*(?:["']([^"']+)["']|([^\s>]+))""", attrs)
        m_size = re.search(r"""size\s*=\s*["']?([^"'\s>]+)["']?""", attrs)
        if m_color:
            styles.append(f"color: {m_color.group(1) or m_color.group(2)}")
        if m_face:
            styles.append(f"font-family: {m_face.group(1) or m_face.group(2)}")
        if m_size:
            raw_size = m_size.group(1)
            _size_map = {"1": "10px", "2": "12px", "3": "14px", "4": "16px", "5": "18px", "6": "22px", "7": "28px"}
            try:
                if raw_size.startswith(("+", "-")):
                    raw_size = str(3 + int(raw_size))  # HTML relative size (base 3)
                px = _size_map.get(raw_size, raw_size)
                if px.endswith("px"):
                    styles.append(f"font-size: {px}")
            except (ValueError, TypeError):
                pass
        return '<span style="' + '; '.join(styles) + ';">' if styles else ""

    cleaned = re.sub(r"<font\b([^>]*)>", _font_repl, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</font\s*>", "</span>", cleaned, flags=re.IGNORECASE)
    # Rich-text spans (color/highlight/font/size) are LEGITIMATE in signatures —
    # the WYSIWYG editor produces <span style="color:#cc4125;">, and a colored
    # signature line must survive saving. Protect styled spans + underline with
    # safe tokens through the tag-strip below, then restore them so the stored
    # markdown keeps the colors (markdown_to_html passes raw inline HTML through).
    _rich_tags = []

    def _protect_rich(m):
        _rich_tags.append(m.group(0))
        return f"\u0000LSSPAN{len(_rich_tags) - 1}\u0000"

    _BLACKISH_COLORS = {
        "black", "#000", "#000000",
        "rgb(0, 0, 0)", "rgb(0,0,0)",
        "rgba(0, 0, 0, 1)", "rgba(0,0,0,1)", "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)",
    }

    def _span_style_is_meaningless(style_val: str) -> bool:
        """True for spans whose style has no visual effect (empty, or only a
        black/default color). Such wrappers just clutter the stored markdown and
        show up as raw <span> tags in the signature editor textarea."""
        s = (style_val or "").strip().strip(";").strip()
        if not s:
            return True
        props = [p.strip() for p in s.split(";") if p.strip()]
        if not props:
            return True
        if len(props) == 1 and props[0].lower().startswith("color"):
            val = props[0].split(":", 1)[1].strip().lower()
            return val in _BLACKISH_COLORS
        return False

    # Match span PAIRS whose content has no nested <span> (flat spans, as the
    # editor produces — one span per line). Meaningless ones (empty/black-only
    # style) are dropped entirely with both tags; meaningful ones are protected
    # with tokens so their styling survives. Nested spans are left for the
    # generic tag-strip below (they stay intact because they were not protected).
    def _handle_span_pair(m):
        open_attrs = m.group(1)
        inner = m.group(2)
        style_m = re.search(r"style\s*=\s*[\"']([^\"']*)[\"']", open_attrs, re.IGNORECASE)
        if style_m and _span_style_is_meaningless(style_m.group(1)):
            return inner  # visually meaningless flat span -> drop both tags
        if style_m:
            _rich_tags.append(f"<span{open_attrs}>")
            open_tok = f"\u0000LSSPAN{len(_rich_tags) - 1}\u0000"
            _rich_tags.append("</span>")
            close_tok = f"\u0000LSSPAN{len(_rich_tags) - 1}\u0000"
            return open_tok + inner + close_tok
        return inner  # bare <span> without styling -> drop both tags

    _SPAN_PAIR = re.compile(
        r"<span\b([^>]*)>((?:[^<]|<(?!/?span\b)[^>]*>)*?)</span\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    cleaned = _SPAN_PAIR.sub(_handle_span_pair, cleaned)
    # Underline (Ctrl+U) is supported by the editor and rendered by markdown_to_html — keep it.
    cleaned = re.sub(r"<u\b[^>]*>|</u\s*>", _protect_rich, cleaned, flags=re.IGNORECASE)
    # Remaining inline tags (font, s, strike, ...) -> strip
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # Restore protected rich-text tags
    for i, tag in enumerate(_rich_tags):
        cleaned = cleaned.replace(f"\u0000LSSPAN{i}\u0000", tag)

    # '--' separator must live on its own line ('--&nbsp;<div>Thanks…' -> '--\nThanks…')
    if re.match(r"^\s*--\s+\S", cleaned):
        cleaned = re.sub(r"^(\s*--)\s+", r"\1\n", cleaned)

    # Collapse blank lines entirely — standard signature format is single-spaced
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    # Normalize trailing whitespace on each line and trim edges
    lines = [ln.rstrip() for ln in cleaned.split("\n")]
    cleaned = "\n".join(lines).strip()
    return cleaned
