"""Roles: one fixed super-admin, admins created only by the super-admin."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

SA = ("calaro@admin.calaro.com", "super-secret-1")


def login(c, email, pw):
    r = c.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def test_superadmin_seeded(c):
    me = c.get("/api/v1/auth/me", headers=login(c, *SA)).json()
    assert me["role"] == "superadmin" and me["is_superadmin"] and me["is_admin"]


def test_superadmin_email_cannot_register(c):
    r = c.post("/api/v1/auth/register", json={"email": "Calaro@Admin.Calaro.com", "password": "whatever123"})
    assert r.status_code == 400


def test_first_user_is_not_admin(c):
    c.post("/api/v1/auth/register", json={"email": "ravi@example.com", "password": "ravi-pass-1", "full_name": "Ravi"})
    me = c.get("/api/v1/auth/me", headers=login(c, "ravi@example.com", "ravi-pass-1")).json()
    assert me["role"] == "user" and not me["is_admin"]
    assert c.get("/api/v1/admin/overview", headers=login(c, "ravi@example.com", "ravi-pass-1")).status_code == 403


def test_superadmin_creates_and_lists_admins(c):
    h = login(c, *SA)
    r = c.post("/api/v1/admin/admins", json={"email": "meena@calaro.com", "full_name": "Meena", "password": "meena-pass-1"}, headers=h)
    assert r.status_code == 201 and r.json()["role"] == "admin"
    # promote an existing user (no password needed)
    r = c.post("/api/v1/admin/admins", json={"email": "ravi@example.com"}, headers=h)
    assert r.status_code == 201 and r.json()["role"] == "admin"
    admins = c.get("/api/v1/admin/admins", headers=h).json()
    assert [a["email"] for a in admins][0] == "calaro@admin.calaro.com"
    assert {"meena@calaro.com", "ravi@example.com"} <= {a["email"] for a in admins}
    actions = [e["action"] for e in c.get("/api/v1/admin/audit", headers=h).json()]
    assert "admin_created" in actions and "admin_promoted" in actions


def test_admin_cannot_manage_admins_but_can_view_console(c):
    h = login(c, "meena@calaro.com", "meena-pass-1")
    assert c.get("/api/v1/admin/overview", headers=h).status_code == 200
    assert c.get("/api/v1/admin/users", headers=h).status_code == 200
    assert c.get("/api/v1/admin/admins", headers=h).status_code == 403
    assert c.post("/api/v1/admin/admins", json={"email": "x@y.com", "password": "12345678"}, headers=h).status_code == 403


def test_revoke_admin_and_superadmin_protected(c):
    h = login(c, *SA)
    admins = {a["email"]: a for a in c.get("/api/v1/admin/admins", headers=h).json()}
    r = c.delete(f"/api/v1/admin/admins/{admins['ravi@example.com']['id']}", headers=h)
    assert r.status_code == 200 and r.json()["role"] == "user"
    r = c.delete(f"/api/v1/admin/admins/{admins['calaro@admin.calaro.com']['id']}", headers=h)
    assert r.status_code == 400


def test_admin_deactivates_user(c):
    c.post("/api/v1/auth/register", json={"email": "spam@example.com", "password": "spam-pass-1"})
    h = login(c, "meena@calaro.com", "meena-pass-1")
    users = c.get("/api/v1/admin/users", params={"q": "spam"}, headers=h).json()
    assert len(users) == 1
    r = c.patch(f"/api/v1/admin/users/{users[0]['id']}", json={"is_active": False}, headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert c.post("/api/v1/auth/login", data={"username": "spam@example.com", "password": "spam-pass-1"}).status_code == 403
    # admins can't deactivate other admins
    sa_id = c.get("/api/v1/auth/me", headers=login(c, *SA)).json()["id"]
    assert c.patch(f"/api/v1/admin/users/{sa_id}", json={"is_active": False}, headers=h).status_code == 403


def test_password_reset_flow(c, caplog):
    from app import crud, database
    import asyncio
    r = c.post("/api/v1/password-reset/request-otp", json={"email": "nobody@example.com"})
    assert r.status_code == 200  # no account enumeration
    otp = asyncio.run(crud.create_password_reset(database.get_database(), "meena@calaro.com"))
    assert c.post("/api/v1/password-reset/reset-password", json={"email": "meena@calaro.com", "otp": "000000", "new_password": "new-pass-123"}).status_code in (400,)
    r = c.post("/api/v1/password-reset/reset-password", json={"email": "meena@calaro.com", "otp": otp, "new_password": "new-pass-123"})
    assert r.status_code == 200
    login(c, "meena@calaro.com", "new-pass-123")


def test_delete_own_meal(c):
    h = login(c, *SA)
    log = c.post("/api/v1/food/logs", json={"raw_text": "2 idli", "items": [{"name": "Idli", "quantity": 2, "unit": "piece", "calories": 116}]}, headers=h).json()
    assert c.delete(f"/api/v1/food/logs/{log['id']}", headers=h).status_code == 204
    assert c.delete(f"/api/v1/food/logs/{log['id']}", headers=h).status_code == 404
