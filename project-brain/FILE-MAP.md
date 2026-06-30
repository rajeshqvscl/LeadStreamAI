# File Map — Full Project Structure

> Legend: 🟢 API route | 🔵 Service | 🟣 Model | 🟠 Utility | ⚪ Config/Other

## Root

```
LeadStreamAI/
├── project-brain/              ← You are here (system documentation)
├── backend/                    ← FastAPI Python backend
│   ├── app/                    ← Application code
│   │   ├── .env                ← Environment variables (DB, API keys, SMTP, OAuth)
│   │   ├── main.py             ← FastAPI app entry + scheduler_loop + maintenance_loop
│   │   ├── database.py         ← DB connection, table creation, schema migrations
│   │   ├── api/                ← API route handlers
│   │   ├── services/           ← Business logic services
│   │   ├── models/             ← Database model/query functions
│   │   ├── utils/              ← Utility functions
│   │   └── prompts/            ← Template files (email_v1.txt)
│   ├── scripts/                ← 45 DB maintenance/debug scripts
│   ├── assets/                 ← PDF attachments (company profiles, teasers)
│   ├── static/                 ← Static files (pitch decks)
│   └── requirements.txt
├── frontend/                   ← React + Vite frontend
│   ├── src/
│   │   ├── pages/              ← 28 page components
│   │   ├── components/         ← Shared components
│   │   ├── services/           ← API client, config
│   │   └── ...
│   └── ...
└── README.md
```

## Backend — API Layer (`backend/app/api/`)

| File | Endpoints | Purpose |
|------|-----------|---------|
| `auth.py` | `/api/auth/login`, `/auth/register`, `/auth/google/*` | Login, signup, Google OAuth flow |
| `leads.py` | `/api/leads/*` | Lead CRUD, bulk ops, unsubscribes, search |
| `drafts.py` | `/api/drafts/*` | AI draft generation, approval, sending, templates |
| `gmail.py` | `/api/gmail/*` | Gmail integration: send, drafts, inbox, reply polling, push notifications |
| `campaigns.py` | `/api/campaigns/*` | Campaign CRUD, recipients |
| `companies.py` | `/api/companies/*` | Company registry, CSV/sheet ingestion, enrichment |
| `intelligence.py` | `/api/intelligence/*` | Auto-enrichment, RAG insights, contradiction detection |
| `admin.py` | `/api/admin/*` | Admin stats, velocity, productivity, audit logs |
| `admin_dashboard.py` | `/api/admin/*` | Admin-specific dashboard data |
| `dashboard.py` | `/api/dashboard/stats` | User dashboard metrics |
| `users.py` | `/api/users/*` | User profile management |
| `metrics.py` | `/api/metrics/*` | Metrics & reporting |
| `prompts.py` | `/api/prompts/*` | Prompt template CRUD |
| `tracking.py` | `/api/track/open/*`, `/api/track/click/*` | Email open/click tracking |
| `reminders.py` | `/api/reminders/*` | User reminders CRUD |
| `ingest.py` | `/api/ingest/*` | Lead ingestion |
| `rocketreach.py` | `/api/rocketreach/*` | People search proxy |
| `family_offices.py` | `/api/family-offices/*` | Family office directory |

## Backend — Services Layer (`backend/app/services/`)

| File | Purpose | Key Functions |
|------|---------|---------------|
| `llm_services.py` | AI integration (Claude, Gemini, Groq) | `classify_reply()`, `generate_email()`, `generate_followup()`, `classify_lead()` |
| `email_service.py` | Email sending | `send_email()` — dispatches via Gmail API, SMTP, or Resend; `check_scheduled_emails()` |
| `google_service.py` | Google APIs | `get_gmail_service()`, `get_calendar_service()`, `get_drive_service()`, `register_gmail_watch()`, `extract_message_body()`, `extract_attachments()` |
| `followup_service.py` | Follow-up engine | `process_outreach_sequences()` — picks leads due for follow-ups, generates content, sends |
| `agent_service.py` | Autonomous agent | Contradiction detection, report generation |
| `campaign_tracking.py` | Campaign tracking | Recipient management, event logging |
| `vision_service.py` | Screenshot→email template | Reverse-engineers email templates from screenshots |
| `rocketreach_service.py` | People search | RocketReach API wrapper with rate limiting |

## Backend — Models Layer (`backend/app/models/`)

| File | Purpose |
|------|---------|
| `lead.py` | Lead CRUD functions, activity log operations |
| `draft.py` | Email draft insertion |
| `campaign.py` | Campaign CRUD |
| `family_office.py` | Family office CRUD + CSV sync |
| `prompt.py` | Prompt template CRUD |

## Backend — Utils (`backend/app/utils/`)

| File | Purpose |
|------|---------|
| `classification.py` | Lead classification (Client/Investor) + sector inference via keyword matching |

## Backend — Scripts (`backend/scripts/`)

45 utility scripts for:
- **DB maintenance**: audit, cleanup, schema checking, export
- **Template management**: Palak signatures, Yashika/Agnitech templates
- **User management**: lead processing, user operations
- **Testing**: API testing, connection tests, PDF fixing
- **Schema**: inspecting leads_raw columns, user columns

## Frontend — Pages (`frontend/src/pages/`)

| File | Purpose |
|------|---------|
| `Dashboard.jsx` | Main dashboard with charts, inbox messages, admin stats (~1259 lines) |
| `Leads.jsx` | Lead table with filtering, search, bulk actions |
| `LeadDetail.jsx` | Single lead view/edit with activity log |
| `Emails.jsx` | Email drafts queue with approval workflow |
| `EditEmail.jsx` | Rich email editor with AI refinement, template picker |
| `InboundDeals.jsx` | Inbound deal tracking (replied leads) |
| `DealIntelligence.jsx` | AI-powered lead intelligence view |
| `Inbox.jsx` | Gmail inbox view |
| `GmailDrafts.jsx` | Gmail draft management |
| `GmailSent.jsx` | Sent email history |
| `Meetings.jsx` | Meeting scheduling |
| `Followups.jsx` | Follow-up sequence management |
| `Campaigns.jsx` | Campaign management |
| `Prompts.jsx` | Manage AI prompt templates |
| `Metrics.jsx` | Detailed metrics/reporting |
| `MisReportPage.jsx` | MIS report view |
| `RocketReach.jsx` | People search UI |
| `CompanyDatabase.jsx` | Company registry with sheet data |
| `FamilyOffices.jsx` | Family office directory |
| `FamilyOfficeDetail.jsx` | Single family office with linked leads |
| `BulkSearch.jsx` | Bulk lead search |
| `History.jsx` | Admin audit log viewer |
| `Users.jsx` | User management (admin) |
| `AdminDashboard.jsx` | Admin dashboard |
| `AdminLogin.jsx` | Admin-specific login |
| `AdminAuditLogs.jsx` | Admin audit logs |
| `Login.jsx` / `Signup.jsx` | User authentication |
| `GenerateSector.jsx` | Sector-based generation (currently commented) |

## Frontend — Components (`frontend/src/components/`)

| File | Purpose |
|------|---------|
| `Layout.jsx` | App shell with sidebar, topbar, dynamic navigation, reminders panel |
| `DraftTemplatePicker.jsx` | Template selection and preview modal |
| `ErrorBoundary.jsx` | React error boundary |
| `ReminderPanel.jsx` | Sidebar reminders/tasks panel |
| `ToolbarTextarea.jsx` | Rich text editor toolbar with image upload |
| `UploadScreenshotModal.jsx` | Screenshot upload for template reverse-engineering |
