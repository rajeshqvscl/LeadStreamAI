"""
Sector-wise Draft Generation API.
Backs the GenerateSector page: sector cards with coverage counts,
per-sector drafting strategy settings, and bulk AI draft generation.
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, Dict, Any
import threading

from app.database import get_db_connection
from app.utils.auth_helpers import normalize_user_id

router = APIRouter()

import logging
logger = logging.getLogger(__name__)

# Canonical sector catalogue (matches frontend card grid)
SECTORS = [
    ("DEEP_TECH", "Deep Tech"), ("HIGH_TECH", "High Tech"), ("SAAS", "SAAS"),
    ("DEFENCE_TECH", "Defence Tech"), ("TRAVEL", "Travel"), ("AUTOMOTIVE", "Automotive"),
    ("AI_INFRA", "AI Infra"), ("AI_INTEL", "AI Intelligence"), ("GEN_AI", "Generative AI"),
    ("ESPORTS", "Esports"), ("ENT_APP", "Enterprise Applications"),
    ("ENT_SW", "Enterprise Software"), ("EDTECH", "EdTech"),
    ("PHARMA", "Pharmaceutical"), ("NUTRA", "Nutraceutical"), ("CHEMICAL", "Chemical"),
    ("FOOD_EXT", "Food Extracts"), ("TEXTILE", "Textile"),
]

_NOT_SENT_STATUSES = "('SENT','OPENED','CLICKED','REPLIED','CLOSED','BOUNCED','SCHEDULED')"

# Leads that still need a draft generated for them
_NEEDING_WHERE = f"""
    lr.email_draft IS NULL
    AND COALESCE(lr.email_status, '') NOT IN {_NOT_SENT_STATUSES}
    AND (lr.email_opt_in IS NULL OR lr.email_opt_in = TRUE)
    AND (lr.is_unsubscribed IS NULL OR lr.is_unsubscribed = FALSE)
    AND lr.email NOT IN (SELECT email FROM unsubscribe_list)
"""


def _ensure_sector_strategies_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sector_strategies (
            sector TEXT PRIMARY KEY,
            context TEXT DEFAULT '',
            strategy TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()


@router.get("/generate/sectors")
def get_sectors(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns all sector cards with needing-emails counts and saved strategies."""
    uid = normalize_user_id(user_id)

    # L1 micro-cache (0ms) → L2 Redis (60s) — fires on every page load; 3 DB queries otherwise
    import json as _json
    from app.utils.microcache import mc_get, mc_set
    mkey = f"gsectors:{uid or 'anon'}"
    hit = mc_get(mkey)
    if hit is not None:
        return hit
    try:
        from app.api.companies import redis_available, redis_client
        cache_key = f"generate:sectors:{uid or 'anon'}"
        if redis_available and redis_client:
            cached = redis_client.get(cache_key)
            if cached:
                parsed = _json.loads(cached)
                mc_set(mkey, parsed, 60)
                return parsed
    except Exception:
        redis_available, redis_client, cache_key = False, None, None

    conn = get_db_connection()
    try:
        _ensure_sector_strategies_table(conn)
        cur = conn.cursor()

        # Saved strategy settings
        cur.execute("SELECT sector, context, strategy FROM sector_strategies")
        strategies = {}
        for r in cur.fetchall():
            v = list(r.values()) if isinstance(r, dict) else list(r)
            strategies[v[0]] = {"context": v[1] or "", "strategy": v[2] or ""}

        # Per-sector lead stats (user-scoped unless admin)
        where_user = "AND lr.user_id = %s" if uid else ""
        params = [uid] if uid else []
        cur.execute(f"""
            SELECT COALESCE(LOWER(TRIM(lr.sector)), '') AS sec,
                   COUNT(*) AS total,
                   SUM(CASE WHEN {_NEEDING_WHERE} THEN 1 ELSE 0 END) AS needing
            FROM leads_raw lr
            WHERE 1=1 {where_user}
            GROUP BY COALESCE(LOWER(TRIM(lr.sector)), '')
        """, params)
        stats = {}
        for r in cur.fetchall():
            v = list(r.values()) if isinstance(r, dict) else list(r)
            stats[v[0]] = {"total": int(v[1] or 0), "needing": int(v[2] or 0)}
        cur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    # Free-text sectors not in the catalogue get appended as custom cards
    known = {key.lower() for key, _ in SECTORS}
    extra = []
    for sec, s in stats.items():
        if sec and sec not in known and not any(sec in k for k in known):
            extra.append((sec.upper(), sec.replace("_", " ").title()))

    cards = []
    for key, display in list(SECTORS) + extra:
        st = stats.get(key.lower(), {})
        saved = strategies.get(key, {})
        matched_total, matched_needing = st.get("total", 0), st.get("needing", 0)
        # Fuzzy: count leads whose sector text contains this key too
        for sec, s in stats.items():
            if sec != key.lower() and key.lower() in sec:
                matched_total += s["total"]; matched_needing += s["needing"]
        cards.append({
            "sector": key,
            "display_name": display,
            "count": matched_needing,
            "total": matched_total,
            "context": saved.get("context", ""),
            "strategy": saved.get("strategy", ""),
        })

    # Campaign dropdown options
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM campaigns WHERE is_active = TRUE ORDER BY name")
    campaigns = []
    for r in cur.fetchall():
        v = list(r.values()) if isinstance(r, dict) else list(r)
        campaigns.append({"id": v[0], "name": v[1]})
    cur.close()
    conn.close()

    result = {"sectors": cards, "campaigns": campaigns}
    mc_set(mkey, result, 60)
    try:
        if redis_available and redis_client:
            redis_client.setex(cache_key, 60, _json.dumps(result))
    except Exception:
        pass
    return result


@router.post("/generate/bulk")
def bulk_generate_for_sector(req: Dict[str, Any], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Kicks off background AI draft generation for leads in a sector that lack drafts."""
    uid = normalize_user_id(user_id)
    sector_key = str(req.get("sector", "")).strip()
    if not sector_key:
        raise HTTPException(status_code=400, detail="sector is required")
    limit = min(int(req.get("limit") or req.get("batch_limit") or 15), 50)

    conn = get_db_connection()
    cur = conn.cursor()
    where_user = "AND lr.user_id = %s" if uid else ""
    params = [uid] if uid else []
    cur.execute(f"""
        SELECT lr.id FROM leads_raw lr
        WHERE LOWER(TRIM(lr.sector)) LIKE %s
          AND {_NEEDING_WHERE}
          {where_user}
        ORDER BY lr.id
        LIMIT %s
    """, tuple([f"%{sector_key.lower()}%"] + params + [limit]))
    lead_ids = [list(r.values())[0] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()

    if not lead_ids:
        return {"success": True, "queued": 0, "message": f"No leads needing drafts in {sector_key}"}

    def _run():
        from app.api.drafts import generate_email_internal, DraftRequest
        ok = fail = 0
        for lid in lead_ids:
            try:
                res = generate_email_internal(DraftRequest(lead_id=lid), uid)
                if "error" in res:
                    fail += 1
                else:
                    ok += 1
            except Exception as ge:
                logger.error(f"Sector bulk gen failed for lead {lid}: {ge}")
                fail += 1
        logger.info(f"Sector bulk generation '{sector_key}' done: ok={ok}, failed={fail}")
        # Counts changed — drop the sectors caches so cards refresh
        from app.utils.microcache import mc_invalidate_prefix
        mc_invalidate_prefix("gsectors:")
        try:
            from app.api.companies import redis_available, redis_client
            if redis_available and redis_client:
                redis_client.delete(f"generate:sectors:{uid or 'anon'}")
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return {"success": True, "queued": len(lead_ids), "message": f"Generation started for {len(lead_ids)} leads"}


@router.post("/generate/save-settings")
def save_sector_settings(req: Dict[str, Any], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Saves per-sector drafting context/strategy overrides."""
    sector_key = str(req.get("sector", "")).strip()
    if not sector_key:
        raise HTTPException(status_code=400, detail="sector is required")

    # Accept both nested settings object and flat keys
    settings = req.get("settings") or {}
    context = str(settings.get("context") or req.get("context") or "")
    strategy = str(settings.get("strategy") or req.get("strategy") or "")

    conn = get_db_connection()
    try:
        _ensure_sector_strategies_table(conn)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sector_strategies (sector, context, strategy, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (sector) DO UPDATE SET context = EXCLUDED.context,
                strategy = EXCLUDED.strategy, updated_at = NOW()
        """, (sector_key, context, strategy))
        conn.commit()
        cur.close()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
