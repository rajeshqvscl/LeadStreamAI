# System Architecture

## Tech Stack

```
Frontend         Backend              Database       External Services
┌─────────┐     ┌──────────────┐     ┌────────┐     ┌──────────────┐
│ React 19 │────▶ FastAPI      │────▶│PostgreSQL│────▶│ Gmail API    │
│ Vite 8   │     │ Gunicorn     │     │ (Neon) │     │ Google Drive │
│ Tailwind4│     │ Redis        │     └────────┘     │ Google Cal   │
│ Recharts │     └──────────────┘                    │ Resend       │
└─────────┘                                          │ Claude/Gemini│
                                                     │ Groq (LLM)   │
                                                     │ RocketReach  │
                                                     │ RAG System   │
                                                     └──────────────┘
```

## Component Overview

```mermaid
graph TB
    subgraph "Frontend (React)"
        P[Pages - 28 screens]
        C[Components - Layout, Template Picker, etc.]
        S[Services - API client, followupConfig]
    end

    subgraph "Backend (FastAPI)"
        API[API Layer - 18 router files]
        SVC[Services Layer - 8 services]
        MOD[Models Layer - 5 models]
        UTIL[Utils - classifiers]
        SCH[Background Scheduler]
    end

    subgraph "Database (PostgreSQL)"
        LR[leads_raw]
        US[users]
        AL[activity_log]
        CP[campaigns]
        PR[prompts]
        GM[gmail_processed_messages]
        UL[unsubscribe_list]
    end

    subgraph "External"
        GMAIL[Gmail API]
        LLM[Claude / Gemini / Groq]
        RESEND[Resend]
        RR[RocketReach]
        RAG[RAG Engine]
    end

    P --> API
    API --> SVC
    SVC --> MOD
    SVC --> LLM
    SVC --> GMAIL
    SVC --> RESEND
    SVC --> RR
    SVC --> RAG
    MOD --> LR
    MOD --> AL
    SCH --> SVC
```

## Request Flow (Typical)

```mermaid
sequenceDiagram
    Browser->>+FastAPI: GET /api/leads/
    FastAPI->>+PostgreSQL: Query leads_raw
    PostgreSQL-->>-FastAPI: Lead rows
    FastAPI->>+Redis: Cache check/set
    Redis-->>-FastAPI: Cached/stored
    FastAPI-->>-Browser: JSON response
```

## Background Scheduler

Runs every 10 seconds via `asyncio.to_thread()` in `main.py`:

```mermaid
graph LR
    T0[Start] --> T1[Poll Gmail for Replies]
    T1 --> T2[Check Scheduled Emails]
    T2 --> T3[Process Follow-up Sequences]
    T3 --> T4[Sleep 10s]
    T4 --> T0
```

**Order matters**: Replies are checked BEFORE follow-ups are sent to prevent sending a follow-up to someone who just replied.

## Deployment

- **Backend**: Render (Gunicorn + Uvicorn workers)
- **Frontend**: Render (Static site, Vite build)
- **Database**: Neon (PostgreSQL)
- **Redis**: Render Redis (caching, rate limiting)
- **Environment vars**: `.env` in `backend/app/.env`

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Per-user data isolation | `(email, user_id)` unique constraint — same email can exist for different users |
| Push + Poll reply detection | Push is real-time but Google can throttle; poll is reliable fallback every 10s |
| Cross-account stop | When a reply is detected, the same email and domain are stopped across all 5 accounts |
| Separate activity_log | Full audit trail independent of lead record updates |
| AI classification in reply handler | Every inbound reply is AI-classified for intent (INTERESTED, NOT_INTERESTED, etc.) |
