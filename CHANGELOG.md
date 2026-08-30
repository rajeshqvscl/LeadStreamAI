# Changelog

## [Unreleased] — 2026-08-27

### Bug Fixes
- **auth.py**: Login + refresh endpoints now return `image_width` and `image_height` in user object (previously missing, causing 400px fallback in SignatureEditor preview)
- **api.js / api.ts**: Token refresh MERGE fix — `{ ...existing, ...response.data.user }` prevents overwriting local user data
- **drafts.py `markdown_to_html()`**: Added `line-height:1.2` to `<table>`, `<th>`, `<td>` elements to fix excessive row spacing in sent emails (outer wrapper `email_service.py:753` sets `line-height:1.6` which cascades into tables)
- **ToolbarTextarea.jsx**: Context menu `onMouseDown` + `preventDefault`/`stopPropagation` prevents editor blur from destroying DOM before action executes
- **ToolbarTextarea.jsx**: `tableMenuDataRef` (useRef) stores table DOM reference, preventing stale reference issues across renders
- **ToolbarTextarea.jsx**: `handleEditorBlur` skips `syncFromEditor()` while context menu is open, preventing DOM rebuild during menu interaction
- **ToolbarTextarea.jsx**: Row move uses `row.parentNode.insertBefore()` instead of `table.insertBefore()` — browsers wrap `<tr>` in implicit `<tbody>`

### Features
- **Settings.jsx**: Image width (100px–600px) and height (auto/50px–600px) dropdowns for user preference
- **EditEmail.jsx**: `getImgSizes()` IIFE reads Settings user's `image_width`/`image_height`; `renderEmailPreview` applies them to ALL images (including HTML branch)
- **SignatureEditor.jsx**: `mdToPreviewHtml` applies `sigImgW`/`sigImgH` to ALL `<img>` tags
- **ToolbarTextarea.jsx**: Table column resize via drag on right border of any cell (cursor: `col-resize`)
- **ToolbarTextarea.jsx**: Right-click context menu inside tables with: Move Row Up/Down, Move Col Left/Right, Insert Row Above/Below, Insert Col Left/Right, Delete Row/Col, Delete Table
- **drafts.py `_extract_body_attachments`**: Now scans `<img src>` tags for logo images (not just CID references)
- **Reviews queue**: Duplicate summary banner with sender filter; `NOT EXISTS` subquery + merged count queries for performance

### Performance
- **drafts.py `get_pending_drafts`**: Removed unused `markdown_to_html()` call for all 60 drafts (biggest win)
- **drafts.py `get_pending_drafts`**: Changed `NOT IN` to `NOT EXISTS` for unsubscribe subquery
- **drafts.py `get_pending_drafts`**: Merged 3 separate count queries into 1 with window functions

### Architecture
- `api.js` (not `api.ts`) is the actual file bundled by Vite — `api.ts` is unused dead code
- `ToolbarTextarea.jsx` is the shared editor used by 7 pages — changes here affect: EditEmail, GmailDrafts, Prompts, Followups, Signatures, SignatureEditor, UploadScreenshotModal

### Files Changed
| File | Changes |
|------|---------|
| `backend/app/api/auth.py` | Login SELECT + return includes `image_width`/`image_height`; refresh return includes `image_width`/`image_height` |
| `backend/app/api/drafts.py` | `markdown_to_html` table `line-height:1.2`; `_extract_body_attachments` img scanning; `get_pending_drafts` perf |
| `backend/app/services/email_service.py` | No changes (outer wrapper `line-height:1.6` is original) |
| `frontend/src/services/api.js` | Token refresh merge fix |
| `frontend/src/pages/EditEmail.jsx` | `getImgSizes()` IIFE, `renderEmailPreview` image propagation |
| `frontend/src/components/SignatureEditor.jsx` | `mdToPreviewHtml` applies sig dimensions to all `<img>` |
| `frontend/src/components/ToolbarTextarea.jsx` | Table resize, context menu, row/col move, `handleEditorBlur` |
| `frontend/src/pages/Settings.jsx` | Image width/height dropdowns |

### Tests Added
| File | Coverage |
|------|----------|
| `backend/tests/unit/test_auth_image_dimensions.py` | Login + refresh endpoints return `image_width`/`image_height` |
| `backend/tests/unit/test_drafts_optimizations.py` | `markdown_to_html` table `line-height:1.2` |
| `backend/tests/unit/test_image_dimensions.py` | Image dimension defaults |
| `frontend/e2e/review-queue.spec.ts` | Review queue loads without JS errors |

### Known Limitations
- Column resize is client-side only (not persisted)
- Context menu does not work in Firefox (contentEditable + onContextMenu differences)
- `api.ts` is dead code — Vite resolves `.js` before `.ts`
