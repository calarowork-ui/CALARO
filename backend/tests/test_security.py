"""Input validation, login lockout, rate limits and session revocation."""
import pytest
from fastapi.testclient import TestClient

from app.core.ratelimit import limiter
from app.main import app

SA = ("calaro@admin.calaro.com", "super-secret-1")


def login(c, email, pw):
    return c.post("/api/v1/auth/login", data={"username": email, "password": pw})


def bearer(r):
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("pw", ["short1", "onlyletters", "12345678", " padded-pass1 ", "x" * 129 + "1"])
def test_weak_passwords_rejected(c, pw):
    r = c.post("/api/v1/auth/register", json={"email": "weak@example.com", "password": pw})
    assert r.status_code == 422


@pytest.mark.parametrize("body", [
    {"email": "not-an-email", "password": "good-pass1"},
    {"email": "x@example.com", "password": "good-pass1", "full_name": "<script>alert(1)</script>"},
    {"email": "x@example.com", "password": "good-pass1", "full_name": "a" * 81},
    {"email": "x@example.com", "password": "good-pass1", "preferred_language": "xx"},
])
def test_bad_signup_fields_rejected(c, body):
    assert c.post("/api/v1/auth/register", json=body).status_code == 422


def test_meal_payload_limits(c):
    c.post("/api/v1/auth/register", json={"email": "limits@example.com", "password": "limits-pass1"})
    h = bearer(login(c, "limits@example.com", "limits-pass1"))
    item = {"name": "Idli", "quantity": 2, "unit": "piece", "calories": 116}
    ok = c.post("/api/v1/food/logs", json={"raw_text": "2 idli", "items": [item]}, headers=h)
    assert ok.status_code == 200
    bad = [
        {"raw_text": "", "items": [item]},
        {"raw_text": "x", "items": []},
        {"raw_text": "x", "items": [item] * 31},
        {"raw_text": "x" * 1001, "items": [item]},
        {"raw_text": "x", "items": [{**item, "quantity": -1}]},
        {"raw_text": "x", "items": [{**item, "calories": 99999}]},
        {"raw_text": "x", "items": [item], "language": "zz"},
    ]
    for b in bad:
        assert c.post("/api/v1/food/logs", json=b, headers=h).status_code == 422, b
    assert c.put("/api/v1/auth/profile", json={"age": 7}, headers=h).status_code == 422
    assert c.put("/api/v1/auth/profile", json={"sex": "other-value"}, headers=h).status_code == 422


def test_login_lockout_after_five_failures(c):
    c.post("/api/v1/auth/register", json={"email": "lock@example.com", "password": "lock-pass1"})
    for _ in range(5):
        assert login(c, "lock@example.com", "wrong-pass1").status_code == 401
    r = login(c, "lock@example.com", "lock-pass1")  # even the right password waits
    assert r.status_code == 429 and "paused" in r.json()["detail"] and int(r.headers["retry-after"]) > 0
    # other accounts are unaffected
    assert login(c, *SA).status_code == 200


def test_success_clears_failures(c):
    c.post("/api/v1/auth/register", json={"email": "clear@example.com", "password": "clear-pass1"})
    for _ in range(4):
        login(c, "clear@example.com", "nope-pass1")
    assert login(c, "clear@example.com", "clear-pass1").status_code == 200
    for _ in range(4):
        login(c, "clear@example.com", "nope-pass1")
    assert login(c, "clear@example.com", "clear-pass1").status_code == 200


def test_password_reset_rate_limited(c):
    limiter.reset()
    codes = [c.post("/api/v1/password-reset/request-otp", json={"email": "flood@example.com"}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_otp_format_checked(c):
    r = c.post("/api/v1/password-reset/reset-password", json={"email": "a@b.com", "otp": "12ab", "new_password": "good-pass1"})
    assert r.status_code == 422


def test_session_revoked_on_password_reset_and_deactivation(c):
    import asyncio
    from app import crud, database
    c.post("/api/v1/auth/register", json={"email": "revoke@example.com", "password": "revoke-pass1"})
    h = bearer(login(c, "revoke@example.com", "revoke-pass1"))
    assert c.get("/api/v1/auth/me", headers=h).status_code == 200
    otp = asyncio.run(crud.create_password_reset(database.get_database(), "revoke@example.com"))
    c.post("/api/v1/password-reset/reset-password", json={"email": "revoke@example.com", "otp": otp, "new_password": "revoke-pass2"})
    assert c.get("/api/v1/auth/me", headers=h).status_code == 401  # old session ended
    h2 = bearer(login(c, "revoke@example.com", "revoke-pass2"))
    sa = bearer(login(c, *SA))
    uid = c.get("/api/v1/auth/me", headers=h2).json()["id"]
    c.patch(f"/api/v1/admin/users/{uid}", json={"is_active": False}, headers=sa)
    assert c.get("/api/v1/auth/me", headers=h2).status_code in (401, 403)


def test_token_expiry_is_short(c):
    import jwt
    from app.core.config import settings
    tok = login(c, *SA).json()["access_token"]
    claims = jwt.decode(tok, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["exp"] - claims["iat"] <= 12 * 3600 + 5


def test_tampered_token_rejected(c):
    tok = login(c, *SA).json()["access_token"]
    bad = tok[:-4] + ("AAAA" if not tok.endswith("AAAA") else "BBBB")
    assert c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_vaani_rate_limit(c):
    limiter.reset()
    c.post("/api/v1/auth/register", json={"email": "chatty@example.com", "password": "chatty-pass1"})
    h = bearer(login(c, "chatty@example.com", "chatty-pass1"))
    codes = [c.post("/api/v1/vaani/text", json={"text": "idli", "lang": "en", "speak": False}, headers=h).status_code for _ in range(31)]
    assert codes.count(200) == 30 and codes[-1] == 429
