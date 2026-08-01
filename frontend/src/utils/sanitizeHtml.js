import DOMPurify from 'dompurify';

/**
 * Sanitizes untrusted HTML (email bodies, replies, drafts) before it is
 * injected into the DOM via dangerouslySetInnerHTML.
 *
 * DOMPurify strips <script>, <iframe>, event handlers (onerror, onclick...),
 * javascript: URLs and other XSS vectors. A conservative allow-list of
 * formatting tags keeps email rendering intact.
 */
export function sanitizeHtml(html) {
  if (!html) return '';
  return DOMPurify.sanitize(String(html), {
    ALLOWED_TAGS: [
      'a', 'b', 'strong', 'em', 'i', 'u', 'p', 'br', 'span', 'div',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote',
      'img', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'hr', 'sub', 'sup',
      'code', 'pre', 'font',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'src', 'alt', 'title', 'width', 'height',
      'style', 'class', 'id', 'align', 'valign', 'colspan', 'rowspan', 'color',
    ],
  });
}
