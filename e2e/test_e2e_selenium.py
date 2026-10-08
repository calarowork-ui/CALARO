"""CALARO end-to-end tests (Selenium + Chrome).

Run against the Docker stack:
    pip install -r e2e/requirements.txt
    set E2E_SUPER_PASS=<your super-admin password>      (PowerShell: $env:E2E_SUPER_PASS="...")
    python -m pytest e2e -v

Tests run in file order; later ones reuse the member created earlier.
"""
import json
import os
import time
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from conftest import ART, SUPER_EMAIL, SUPER_PASS, UI, latest_otp, make_driver

AXE = (Path(__file__).parent / "vendor" / "axe.min.js").read_text(encoding="utf-8")
A11Y_RESULTS = {}


def run_axe(ui: UI, label: str):
    ui.d.execute_script(AXE)
    res = ui.d.execute_async_script(
        "const done = arguments[0]; axe.run(document, {runOnly: ['wcag2a','wcag2aa']}).then(r => done(r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help}))));")
    A11Y_RESULTS[label] = res
    (ART / "a11y.json").write_text(json.dumps(A11Y_RESULTS, indent=2))
    return res


# ------------------------------------------------------------------ sign-up and validation
def test_01_sign_in_page_loads(ui):
    ui.open("/")
    h1 = ui.wait("h1")
    assert "Say what you ate" in h1.text
    assert ui.d.title == "CALARO"
    assert ui.wait("#email") and ui.wait("#pw")
    v = run_axe(ui, "sign-in")
    assert not [x for x in v if x["impact"] == "critical"], v


def test_02_signup_validation(ui, ids):
    ui.open("/")
    ui.click(text="Create an account")
    ui.type("#email", "not-an-email")
    ui.type("#pw", "abcdefgh")
    # the browser's own email check would block submit; bypass it to test the app's checks
    ui.d.execute_script("document.querySelector('form').noValidate = true")
    ui.click("button[type=submit]")
    ui.wait_text("valid email address")
    ui.type("#email", ids["member"])
    ui.click("button[type=submit]")
    ui.wait_text("stronger password")
    rules = [li.get_attribute("class") or "" for li in ui.all(".pw-rules li")]
    assert rules.count("met") == 2  # length + letter met, number missing
    ui.type("#pw", "abcdefg1")
    rules = [li.get_attribute("class") or "" for li in ui.all(".pw-rules li")]
    assert rules.count("met") == 3
    ui.shot("02_password_rules")


def test_03_register_goes_to_onboarding(ui, ids):
    ui.register("Lakshmi E2E", ids["member"], ids["pw"], lang="ta")
    ui.wait(".onb-main")
    ui.wait_text("About you")
    ui.click(text="Continue")
    ui.wait_text("Enter an age between 13 and 100")
    ui.shot("03_onboarding_validation")


def test_04_duplicate_signup_rejected(ui, ids):
    ui.register("Someone", ids["member"], ids["pw"])
    ui.wait_text("already exists")


def test_05_complete_onboarding_and_plan(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.wait(".onb-main")
    ui.type("#o-age", "34")
    ui.click(text="Female")
    ui.type("#o-h", "158")
    ui.type("#o-w", "68")
    ui.click(text="Continue")
    ui.click(text="Lose weight")
    ui.type("#o-t", "75")  # above current weight: should be refused
    ui.click(text="Continue")
    ui.wait_text("target should be below")
    ui.type("#o-t", "60")
    ui.click(text="Continue")
    ui.click(text="On my feet sometimes")
    ui.click(text="Evening snack")
    ui.click(text="Continue")
    ui.click(text="Vegetarian", tag="button")
    ui.click(text="South Indian")
    ui.click(text="Continue")
    ui.click(text="Prediabetes")
    ui.click(text="Fried snacks")
    ui.click(text="See my plan")
    ui.wait(".plan-kcal", timeout=15)
    kcal = int(ui.wait(".plan-kcal").text.split()[0].replace(",", ""))
    assert 1200 <= kcal <= 2000
    ui.wait_text("The sugar in your chai")
    ui.wait_text("Prediabetes")
    ui.shot("05_plan")
    v = run_axe(ui, "plan")
    assert not [x for x in v if x["impact"] == "critical"], v
    ui.click(text="Start logging meals")
    ui.wait(".thali")
    ui.wait_text(f"of {kcal:,} kcal".replace(",", ","))


# ------------------------------------------------------------------ logging meals
def test_06_log_meal_in_tamil(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.wait(".thali")
    ui.click("[role=radio][lang=ta]")
    ui.type(".type-row input", "ரெண்டு இட்லி, ஒரு வடை, ஒரு கிண்ணம் சாம்பார்")
    ui.click(".type-row button[type=submit]")
    ui.wait(".slip-row")
    rows = ui.all(".slip-row")
    assert len(rows) == 3, [r.text for r in rows]
    first_kcal = ui.all(".slip-row .kcal b")[0].text
    ui.click("button[aria-label^='More']")
    assert ui.all(".slip-row .kcal b")[0].text != first_kcal  # quantity change recalculates
    ui.shot("06_meal_matched")
    ui.click(text="Save meal")
    ui.wait(".ledger-item")
    assert "இட்லி" in ui.wait(".ledger-item").text
    total = ui.d.find_element(By.CSS_SELECTOR, ".thali text[font-size='58']").text
    assert int(total.replace(",", "")) > 300
    v = run_axe(ui, "today")
    assert not [x for x in v if x["impact"] == "critical"], v


def test_07_add_dish_by_search(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.type(".add-food input", "dosa")
    ui.click(".suggest button")
    ui.wait(".slip-row")
    assert "Dosa" in ui.wait(".slip-row").text
    ui.click(text="Discard")
    ui.gone(".slip-row")


def test_08_script_injection_is_shown_as_text(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    payload = '<img src=x onerror="window.__xss=1"> idli'
    ui.type(".type-row input", payload)
    ui.click(".type-row button[type=submit]")
    ui.wait(".slip-row")
    ui.click(text="Save meal")
    ui.wait_text("onerror")  # rendered literally in the ledger
    assert ui.d.execute_script("return window.__xss || 0") == 0


def test_09_history_shows_meals(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.click(text="History")
    ui.wait(".day-group")
    assert len(ui.all(".day-group .ledger-item")) >= 2
    ui.shot("09_history")


def test_10_delete_meal(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.wait(".ledger-item")
    before = len(ui.all(".ledger-item"))
    ui.click(".ledger-item button[aria-label='Delete this meal']")
    time.sleep(1.0)
    assert len(ui.all(".ledger-item")) == before - 1


def test_11_profile_update_recalculates_goal(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.click(text="Profile")
    w = ui.wait("#w")
    end = time.time() + 10
    while time.time() < end and w.get_attribute("value") != "68":  # wait for the saved profile to load
        time.sleep(0.2)
    old = ui.wait(".goal-card .goal").text
    w.send_keys(Keys.CONTROL, "a")
    w.send_keys("64")
    ui.click(text="Save profile")
    ui.wait_text("Saved")
    time.sleep(0.8)
    assert ui.wait(".goal-card .goal").text != old


# ------------------------------------------------------------------ access control and sessions
def test_12_member_cannot_reach_admin(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    labels = " ".join(b.text for b in ui.all(".nav-item"))
    assert "Admin" not in labels
    status, _ = ui.api("GET", "/admin/overview")
    assert status == 403
    status, _ = ui.api("POST", "/admin/admins", {"email": "x@y.com", "password": "abcdef12"})
    assert status == 403


def test_13_sign_out_clears_session(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.sign_out()
    assert ui.d.execute_script("return localStorage.getItem('calaro_token')") is None
    ui.d.refresh()
    ui.wait("#email")


def test_14_expired_session_returns_to_sign_in(ui, ids):
    ui.sign_in(ids["member"], ids["pw"])
    ui.d.execute_script("localStorage.setItem('calaro_token', localStorage.getItem('calaro_token').slice(0, -3) + 'xyz')")
    ui.click(text="History")
    ui.wait("#email")
    ui.wait_text("Your session ended")


def test_15_idle_timeout_signs_out(ui, ids):
    ui.open("/")
    ui.d.execute_script("localStorage.setItem('calaro_e2e_idle_min', '0.1')")  # 6 seconds, test builds only
    ui.sign_in(ids["member"], ids["pw"])
    ui.wait(".thali")
    time.sleep(9)
    ui.wait("#email", timeout=10)
    ui.wait_text("without activity")
    ui.shot("15_idle_signed_out")
    ui.d.execute_script("localStorage.removeItem('calaro_e2e_idle_min')")


def test_16_login_lockout(ui, ids):
    ui.open("/")
    for i in range(5):
        ui.type("#email", ids["member"])
        ui.type("#pw", f"Wrong-pass-{i}")
        ui.click("button[type=submit]")
        ui.wait_text("incorrect")
    ui.type("#pw", ids["pw"])
    ui.click("button[type=submit]")
    ui.wait_text("sign-in is paused")
    ui.shot("16_lockout")


# ------------------------------------------------------------------ admins
@pytest.mark.skipif(not SUPER_PASS, reason="set E2E_SUPER_PASS")
def test_17_superadmin_console_and_team(ui, ids):
    ui.sign_in(SUPER_EMAIL, SUPER_PASS)
    ui.click(text="Admin console")
    ui.wait(".kpi")
    v = run_axe(ui, "admin")
    assert not [x for x in v if x["impact"] == "critical"], v
    ui.click(text="People")
    ui.wait("table.data")
    ui.click(text="Admin team")
    ui.type("#ae", ids["admin"])
    ui.type("#an", "E2E Admin")
    ui.type("#ap", "Admin-2026-ok")
    ui.click(text="Add admin")
    ui.wait_text("is now an admin")
    ui.wait_text("created admin")
    ui.shot("17_team")


@pytest.mark.skipif(not SUPER_PASS, reason="set E2E_SUPER_PASS")
def test_18_admin_sees_console_not_team(ui, ids):
    ui.sign_in(ids["admin"], "Admin-2026-ok")
    labels = " ".join(b.text for b in ui.all(".nav-item"))
    assert "Admin console" in labels and "Admin team" not in labels
    status, _ = ui.api("GET", "/admin/admins")
    assert status == 403
    ui.click(text="Admin console")
    ui.click(text="Monitoring")
    ui.wait("iframe")
    ui.shot("18_monitoring")


@pytest.mark.skipif(not SUPER_PASS, reason="set E2E_SUPER_PASS")
def test_19_deactivated_member_cannot_sign_in(ui, ids):
    ui.register("Second Member", ids["member2"], ids["pw"])
    ui.wait(".onb-main")
    ui.d.delete_all_cookies()
    ui.d.execute_script("localStorage.clear()")
    ui.sign_in(SUPER_EMAIL, SUPER_PASS)
    ui.click(text="Admin console")
    ui.click(text="People")
    ui.type(".toolbar .input", ids["member2"])
    time.sleep(0.8)
    ui.click(text="Deactivate")
    ui.wait_text("deactivated")
    ui.sign_out()
    ui.sign_in(ids["member2"], ids["pw"], expect_app=False)
    ui.wait_text("deactivated")


@pytest.mark.skipif(not os.environ.get("E2E_OTP_LOG"), reason="set E2E_OTP_LOG to the backend log to read the emailed code")
def test_20_password_reset(ui, ids):
    ui.open("/")
    ui.click(text="Forgot password?")
    ui.type("#email", ids["member"])
    ui.click("button[type=submit]")
    ui.wait("#otp")
    time.sleep(0.8)
    otp = latest_otp(os.environ["E2E_OTP_LOG"], ids["member"])
    assert otp, "no code found in the backend log"
    ui.type("#otp", otp)
    ui.type("#npw", "Thali-2026-new1")
    ui.click("button[type=submit]")
    ui.wait_text("Password updated")
    ids["pw"] = "Thali-2026-new1"


# ------------------------------------------------------------------ phones
def test_21_mobile_layout():
    d = make_driver(390, 844)
    try:
        u = UI(d)
        u.open("/")
        u.wait("#email")
        assert d.execute_script("return document.documentElement.scrollWidth <= window.innerWidth + 1")
        u.d.save_screenshot(str(ART / "21_mobile_signin.png"))
        if SUPER_PASS:
            u.sign_in(SUPER_EMAIL, SUPER_PASS)
            u.wait(".thali")
            assert u.wait(".tabbar").is_displayed()
            assert not u.all(".rail")[0].is_displayed()
            assert d.execute_script("return document.documentElement.scrollWidth <= window.innerWidth + 1")
            u.d.save_screenshot(str(ART / "21_mobile_today.png"))
    finally:
        d.quit()
