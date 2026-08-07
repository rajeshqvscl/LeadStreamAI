/**
 * Forced logo display size — PALAK ONLY.
 *
 * Mirrors backend `_LOGO_FORCED_STYLES` in app/api/drafts.py. Palak's QVSCL
 * logo must always render at 150x150 — even when the stored signature is plain
 * markdown (`![alt](url)`, as produced by a re-save through the editor), where
 * the frontend preview converters would otherwise fall back to max-width:100%
 * and blow the image up to its original size.
 *
 * The map is keyed by the exact asset FILENAME so ONLY this specific logo is
 * affected — every other user's signature images render exactly as before.
 */

const FORCED_LOGO_STYLES = {
  // .jpg is intentional: the asset is a JPEG committed to the repo (served as
  // image/jpeg). The old .webp name returned application/octet-stream on the
  // deployed backend, which browsers/email clients refuse to render.
  'upload_1785476979958_9473.jpg': 'width:150px;height:150px;object-fit:contain;display:block;',
};

/** Resolve the forced inline style for a logo asset URL, else null. */
export function forcedLogoStyle(src) {
  if (!src) return null;
  const fname = String(src)
    .replace(/\/+$/, '')
    .split('/')
    .pop()
    .split('?')[0]
    .split('#')[0];
  return FORCED_LOGO_STYLES[fname] || null;
}

/**
 * Rewrite every <img> in `html` whose src points at a known logo so its style
 * is forced to the fixed size (replacing any existing style). Safe to call on
 * arbitrary HTML — images that don't match a known logo are left untouched.
 */
export function applyForcedLogoStyles(html) {
  if (!html) return html;
  return String(html).replace(/<img\b[^>]*>/gi, (m) => {
    const srcM = m.match(/src\s*=\s*"([^"]+)"/);
    if (!srcM) return m;
    const forced = forcedLogoStyle(srcM[1]);
    if (!forced) return m;
    if (/style\s*=\s*"/i.test(m)) {
      return m.replace(/style\s*=\s*"([^"]*)"/i, `style="${forced}"`);
    }
    return m.replace('<img', `<img style="${forced}"`);
  });
}
