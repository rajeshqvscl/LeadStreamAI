# AGENTS.md — Pre-Commit Checks

Run these before committing ANY code change:

## Frontend (frontend/)
```bash
cd frontend
npm run build          # Catches JSX/syntax errors via Vite/esbuild
npm test               # Runs Vitest unit tests (if any exist)
```

## Backend (backend/)
```bash
cd backend
python -c "import py_compile; py_compile.compile('app/api/auth.py', doraise=True)"
python -c "import py_compile; py_compile.compile('app/api/drafts.py', doraise=True)"
python -c "import py_compile; py_compile.compile('app/api/leads.py', doraise=True)"
python -c "import py_compile; py_compile.compile('app/api/gmail.py', doraise=True)"
python -c "import py_compile; py_compile.compile('app/services/email_service.py', doraise=True)"
```

Or run ALL backend files at once:
```bash
cd backend
python -m py_compile app/api/auth.py && python -m py_compile app/api/drafts.py && python -m py_compile app/api/leads.py && python -m py_compile app/api/gmail.py && python -m py_compile app/services/email_service.py && echo "ALL OK"
```

## Run Backend Tests
```bash
cd backend
pytest tests/unit/ -v
```

## Critical Files (always check syntax before commit)
- `frontend/src/components/ToolbarTextarea.jsx` — shared editor component used by 7 pages
- `frontend/src/pages/EditEmail.jsx` — email preview + signature preview
- `frontend/src/components/SignatureEditor.jsx` — signature editor
- `frontend/src/services/api.js` — token refresh interceptor
- `backend/app/api/auth.py` — login/refresh/preferences endpoints
- `backend/app/api/drafts.py` — draft generation, review queue, send flow
- `backend/app/services/email_service.py` — email sending + HTML wrapping

## Architecture Notes
- `api.js` (not `api.ts`) is the actual file bundled by Vite (see `vite.config.js` line 62)
- `ToolbarTextarea.jsx` is used by: EditEmail, GmailDrafts, Prompts, Followups, Signatures, SignatureEditor, UploadScreenshotModal
- Backend uses psycopg2 DictCursor — `row['col']` or `row.get('col')`, never `row.col`
- `markdown_to_html()` in drafts.py is heavy (~320 lines of regex) — avoid calling in loops
- `heal_draft_content()` in drafts.py does string replacements per draft — avoid calling in loops
