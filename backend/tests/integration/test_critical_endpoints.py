"""
Integration tests for the critical pages that previously 404'd or 500'd.

These run against a stubbed DB (conftest.fake_db) and a bypassed auth layer
(conftest.client), so they verify ROUTING + RESPONSE SHAPE, not live data.
They act as a regression safety net: if a route is removed, double-prefixed,
or collides, these fail.
"""
import pytest


def test_dashboard_stats(client, auth_headers):
    r = client.get("/api/dashboard/stats", headers=auth_headers)
    assert r.status_code == 200, r.text
    # endpoint returns either a dict of stats or a list; assert JSON body present
    assert r.json() is not None


def test_gmail_inbox(client, auth_headers):
    r = client.get("/api/gmail/inbox", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # inbox returns {"emails": [...], ...} or a list
    assert isinstance(body, (dict, list))


def test_reminders_due(client, auth_headers):
    r = client.get("/api/reminders/due", headers=auth_headers)
    assert r.status_code == 200, r.text


def test_reminders_urgent_actions(client, auth_headers):
    r = client.get("/api/reminders/urgent-actions", headers=auth_headers)
    assert r.status_code == 200, r.text


def test_metrics_report(client, auth_headers):
    r = client.get("/api/metrics", params={"period": "all"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # THIS is the regression guard for the /api/metrics Prometheus collision:
    # the report MUST contain a "report" key, not Prometheus text.
    assert "report" in body, f"/api/metrics did not return report JSON: {r.text[:200]}"


def test_users_pilot_settings(client, auth_headers):
    r = client.get("/api/users/pilot-settings", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "auto_pilot_drafts" in body


def test_leads_list(client, auth_headers):
    r = client.get("/api/leads", params={"page": 1, "per_page": 10}, headers=auth_headers)
    assert r.status_code == 200, r.text


def test_companies_list(client, auth_headers):
    r = client.get("/api/companies", headers=auth_headers)
    assert r.status_code == 200, r.text


def test_health_redis(client):
    # Public endpoint (no auth required). Verifies the Redis pool health probe
    # added after the "max number of clients reached" incident.
    r = client.get("/api/health/redis")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "status" in body
    assert "configured" in body
