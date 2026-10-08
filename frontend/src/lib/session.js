import { useEffect, useRef } from "react";

// Minutes of inactivity before CALARO signs you out. Admins get a shorter window.
export const IDLE_MINUTES = Number(import.meta.env.VITE_IDLE_MINUTES || 30);
export const ADMIN_IDLE_MINUTES = Math.min(IDLE_MINUTES, Number(import.meta.env.VITE_ADMIN_IDLE_MINUTES || 15));

const KEY = "calaro_last_active";

// End-to-end test builds only (VITE_E2E=1): allow a tiny idle window so the timeout can be tested.
export function effectiveIdleMinutes(base) {
  if (import.meta.env.VITE_E2E === "1") {
    try {
      const v = Number(localStorage.getItem("calaro_e2e_idle_min"));
      if (v > 0) return v;
    } catch {
      /* ignore */
    }
  }
  return base;
}
const EVENTS = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"];

function read() {
  try {
    return Number(localStorage.getItem(KEY)) || Date.now();
  } catch {
    return Date.now();
  }
}
function write(t) {
  try {
    localStorage.setItem(KEY, String(t)); // shared across tabs
  } catch {
    /* storage blocked: this tab still tracks itself */
  }
}

/** Calls onIdle once after `minutes` without any activity (in any open tab). */
export function useIdleSignOut(enabled, minutes, onIdle) {
  const last = useRef(Date.now());
  const fired = useRef(false);

  useEffect(() => {
    if (!enabled) return undefined;
    fired.current = false;
    last.current = Date.now();
    write(last.current);
    let lastWrite = 0;
    const bump = () => {
      last.current = Date.now();
      if (last.current - lastWrite > 5000) {
        lastWrite = last.current;
        write(last.current);
      }
    };
    EVENTS.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    const limit = minutes * 60 * 1000;
    const check = () => {
      const lastSeen = Math.max(last.current, read());
      if (!fired.current && Date.now() - lastSeen >= limit) {
        fired.current = true;
        onIdle();
      }
    };
    const timer = setInterval(check, Math.min(15000, Math.max(1000, limit / 4)));
    document.addEventListener("visibilitychange", check);
    return () => {
      EVENTS.forEach((e) => window.removeEventListener(e, bump));
      clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
    };
  }, [enabled, minutes, onIdle]);
}

export function passwordProblems(pw, email = "") {
  const out = [];
  if (pw.length < 8) out.push("At least 8 characters");
  if (!/[A-Za-z]/.test(pw)) out.push("At least one letter");
  if (!/\d/.test(pw)) out.push("At least one number");
  if (pw.length > 128) out.push("No more than 128 characters");
  if (pw && pw.trim() !== pw) out.push("No space at the start or end");
  if (email && pw && pw.toLowerCase() === email.toLowerCase()) out.push("Different from your email");
  return out;
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
