"""Grafana cookie handshake, metrics endpoint and JSON request logs."""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app

SA = ("calaro@admin.calaro.com", "super-secret-1")
VERIFY = "/api/v1/admin/monitoring/verify"


def login(c, email, pw):
    r = c.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def session_cookie(c, headers):
    r = c.post("/api/v1/admin/monitoring/session", headers=headers)
    assert r.status_code == 200, r.text
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie and "Path=/grafana" in set_cookie and "samesite=strict" in set_cookie.lower()
    return set_cookie.split(";")[0]


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def test_verify_requires_cookie(c):
    assert c.get(VERIFY).status_code == 401
    assert c.get(VERIFY, headers={"Cookie": "calaro_mon=forged"}).status_code == 401


def test_members_cannot_open_monitoring(c):
    c.post("/api/v1/auth/register", json={"email": "mon-member@example.com", "password": "member-pass1"})
    h = login(c, "mon-member@example.com", "member-pass1")
    assert c.post("/api/v1/admin/monitoring/session", headers=h).status_code == 403


def test_superadmin_gets_grafana_admin(c):
    cookie = session_cookie(c, login(c, *SA))
    r = c.get(VERIFY, headers={"Cookie": cookie})
    assert r.status_code == 200
    assert r.headers["x-webauth-user"] == "calaro@admin.calaro.com" and r.headers["x-webauth-role"] == "Admin"


def test_admin_is_viewer_and_revocation_is_immediate(c):
    sa = login(c, *SA)
    a = c.post("/api/v1/admin/admins", json={"email": "mon-admin@calaro.com", "password": "mon-admin-pass1"}, headers=sa).json()
    cookie = session_cookie(c, login(c, "mon-admin@calaro.com", "mon-admin-pass1"))
    r = c.get(VERIFY, headers={"Cookie": cookie})
    assert r.status_code == 200 and r.headers["x-webauth-role"] == "Viewer"
    c.delete(f"/api/v1/admin/admins/{a['id']}", headers=sa)
    assert c.get(VERIFY, headers={"Cookie": cookie}).status_code == 403


def test_metrics_exposed(c):
    c.post("/api/v1/auth/login", data={"username": "nobody@example.com", "password": "wrong-pass"})
    body = c.get("/metrics").text
    for name in ("http_requests_total", "http_request_duration_seconds_bucket", "calaro_logins_total",
                 "calaro_signups_total", "calaro_users", "calaro_bhashini_request_seconds"):
        assert name in body, name
    assert 'calaro_logins_total{result="failure"}' in body


def test_request_log_is_json(c, caplog):
    from app.core.observability import JsonFormatter
    with caplog.at_level(logging.INFO, logger="calaro.request"):
        c.get("/api/v1/vaani/status")
    recs = [r for r in caplog.records if r.name == "calaro.request" and getattr(r, "route", "") == "/api/v1/vaani/status"]
    assert recs
    line = json.loads(JsonFormatter().format(recs[-1]))
    assert line["status"] == 200 and "duration_ms" in line and line["level"] == "info" and "email" not in line
