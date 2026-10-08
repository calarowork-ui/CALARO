"""Selenium setup for the CALARO end-to-end suite.

Environment variables:
  E2E_BASE_URL      site under test (default http://localhost  -> your Docker stack)
  E2E_SUPER_EMAIL   super-admin email (default calaro@admin.calaro.com)
  E2E_SUPER_PASS    super-admin password (required)
  E2E_OTP_LOG       optional: file where the backend writes mock emails, to test password reset
  CHROME_BIN / CHROMEDRIVER  optional paths; otherwise Selenium Manager finds Chrome
  E2E_HEADED=1      watch the browser
"""
import os
import re
import time
import uuid
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE = os.environ.get("E2E_BASE_URL", "http://localhost").rstrip("/")
SUPER_EMAIL = os.environ.get("E2E_SUPER_EMAIL", "calaro@admin.calaro.com")
SUPER_PASS = os.environ.get("E2E_SUPER_PASS", "")
ART = Path(__file__).parent / "artifacts"
ART.mkdir(exist_ok=True)
RUN = uuid.uuid4().hex[:6]


def make_driver(width=1366, height=900):
    opts = webdriver.ChromeOptions()
    if os.environ.get("CHROME_BIN"):
        opts.binary_location = os.environ["CHROME_BIN"]
    if not os.environ.get("E2E_HEADED"):
        opts.add_argument("--headless=new")
    for a in ("--no-sandbox", "--disable-dev-shm-usage", f"--window-size={width},{height}", "--lang=en-IN"):
        opts.add_argument(a)
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    service = Service(os.environ["CHROMEDRIVER"], service_args=["--disable-build-check"]) if os.environ.get("CHROMEDRIVER") else Service()
    d = webdriver.Chrome(service=service, options=opts)
    d.set_window_size(width, height)
    d.implicitly_wait(0)
    return d


@pytest.fixture
def driver(request):
    d = make_driver()
    yield d
    name = request.node.name.replace("/", "_")
    try:
        d.save_screenshot(str(ART / f"{name}.png"))
    finally:
        d.quit()


class UI:
    """Small helpers so tests read like steps."""

    def __init__(self, d):
        self.d = d

    def open(self, path="/"):
        self.d.get(BASE + path)
        return self

    def wait(self, css, timeout=12, visible=True):
        cond = EC.visibility_of_element_located if visible else EC.presence_of_element_located
        return WebDriverWait(self.d, timeout).until(cond((By.CSS_SELECTOR, css)))

    def wait_text(self, text, timeout=12):
        end = time.time() + timeout
        while time.time() < end:
            if text.lower() in self.d.find_element(By.TAG_NAME, "body").text.lower():
                return True
            time.sleep(0.2)
        raise TimeoutException(f"text not found: {text!r}")

    def gone(self, css, timeout=12):
        WebDriverWait(self.d, timeout).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, css)))

    def click(self, css=None, text=None, tag="button", timeout=12):
        if text is not None:
            xp = f"//{tag}[contains(normalize-space(.), {xpath_literal(text)})]"
            el = WebDriverWait(self.d, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
        else:
            el = WebDriverWait(self.d, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
        self.d.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
        el.click()
        return el

    def type(self, css, value, clear=True):
        el = self.wait(css)
        if clear:
            el.clear()
        el.send_keys(value)
        return el

    def all(self, css):
        return self.d.find_elements(By.CSS_SELECTOR, css)

    def shot(self, name):
        self.d.save_screenshot(str(ART / f"{name}.png"))

    # -------- app flows
    def sign_in(self, email, password, expect_app=True):
        self.open("/")
        self.wait("#email")
        self.type("#email", email)
        self.type("#pw", password)
        self.click("button[type=submit]")
        if expect_app:
            self.wait(".shell, .onb", timeout=15)

    def register(self, name, email, password, lang="ta"):
        self.open("/")
        self.click(text="Create an account")
        self.type("#name", name)
        self.type("#email", email)
        self.type("#pw", password)
        self.d.execute_script(
            "const s=document.querySelector('#lang'); s.value=arguments[0]; s.dispatchEvent(new Event('change',{bubbles:true}))", lang)
        self.click("button[type=submit]")

    def sign_out(self):
        css = ".rail-foot button" if self.d.get_window_size()["width"] > 820 else ".mobile-top button[aria-label='Sign out']"
        for _ in range(3):  # the page may re-render between finding and clicking
            try:
                self.click(css)
                break
            except StaleElementReferenceException:
                time.sleep(0.3)
        self.wait("#email")

    def api(self, method, path, body=None):
        """Call the API from inside the page with the stored token. Returns [status, json]."""
        return self.d.execute_async_script(
            """
            const [m, p, b, done] = arguments;
            fetch('/api/v1' + p, {method: m, headers: {'Content-Type': 'application/json',
              Authorization: 'Bearer ' + (localStorage.getItem('calaro_token') || '')}, body: b ? JSON.stringify(b) : undefined})
              .then(async r => done([r.status, await r.json().catch(() => null)])).catch(e => done([0, String(e)]));
            """, method, path, body)


def xpath_literal(s):
    if "'" not in s:
        return f"'{s}'"
    return "concat('" + s.replace("'", "',\"'\",'") + "')"


@pytest.fixture
def ui(driver):
    return UI(driver)


@pytest.fixture(scope="session")
def ids():
    return {
        "member": f"e2e.member.{RUN}@example.com",
        "member2": f"e2e.member2.{RUN}@example.com",
        "admin": f"e2e.admin.{RUN}@example.com",
        "pw": "Thali-2026-ok",
    }


def latest_otp(log_path, email):
    text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
    idx = text.rfind(email)
    m = re.search(r"letter-spacing:8px;color:#0f3d2e\\?\">(\d{6})<", text[idx:]) if idx >= 0 else None
    if not m:
        m = re.findall(r">(\d{6})<", text[idx:] if idx >= 0 else text)
        return m[0] if m else None
    return m.group(1)
