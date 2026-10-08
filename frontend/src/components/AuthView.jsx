import { useState } from "react";

import { requestPasswordReset, resetPassword } from "../api/auth";
import { FALLBACK_LANGS, errorText } from "../lib/format";
import { EMAIL_RE, passwordProblems } from "../lib/session";
import { BrandMark } from "./Shell";

const VOICES = [
  { said: "ரெண்டு இட்லி, ஒரு வடை, சாம்பார்", lang: "Tamil", kcal: 386 },
  { said: "दो रोटी, एक कटोरी दाल", lang: "Hindi", kcal: 370 },
  { said: "দুটো রুটি আর মাছের ঝোল", lang: "Bengali", kcal: 420 },
  { said: "രണ്ട് പുട്ട്, ഒരു കടല കറി", lang: "Malayalam", kcal: 600 },
];

export function AuthView({ onAuthenticated, notice }) {
  const [mode, setMode] = useState("login"); // login | register | forgot | reset
  const [form, setForm] = useState({ email: "", password: "", full_name: "", lang: "hi", otp: "", new_password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const go = (m) => {
    setMode(m);
    setError("");
    setInfo("");
  };

  const newPw = mode === "register" ? form.password : mode === "reset" ? form.new_password : "";
  const pwProblems = mode === "register" || mode === "reset" ? passwordProblems(newPw, form.email) : [];

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!EMAIL_RE.test(form.email.trim())) {
      setError("Enter a valid email address, like name@example.com.");
      return;
    }
    if (pwProblems.length) {
      setError(`Choose a stronger password: ${pwProblems.join(", ").toLowerCase()}.`);
      return;
    }
    setBusy(true);
    try {
      if (mode === "login" || mode === "register") {
        await onAuthenticated(mode, form);
      } else if (mode === "forgot") {
        await requestPasswordReset(form.email);
        setInfo("If that email has an account, a 6-digit code is on its way. It expires in 15 minutes.");
        setMode("reset");
      } else if (mode === "reset") {
        await resetPassword(form.email, form.otp, form.new_password);
        setInfo("Password updated. Sign in with your new password.");
        setForm((f) => ({ ...f, password: "", otp: "", new_password: "" }));
        setMode("login");
      }
    } catch (err) {
      setError(errorText(err, "Something went wrong. Check your details and try again."));
    } finally {
      setBusy(false);
    }
  };

  const titles = {
    login: ["Sign in", "Sign in"],
    register: ["Create your account", "Create account"],
    forgot: ["Reset your password", "Send code"],
    reset: ["Enter your code", "Set new password"],
  };

  return (
    <div className="auth">
      <section className="auth-story">
        <div className="brand" style={{ padding: 0 }}>
          <BrandMark />
          <span className="brand-name">CALARO</span>
        </div>
        <div>
          <h1>Say what you ate. In your language.</h1>
          <p className="lede">
            CALARO understands Tamil, Hindi, Telugu, Bengali and eight more Indian languages, along with katori, ladle
            and roti counts. It answers out loud, in your language.
          </p>
        </div>
        <div className="voices" aria-label="Examples">
          {VOICES.map((v) => (
            <div className="voice" key={v.lang}>
              <span className="said">{v.said}</span>
              <span className="lang">{v.lang} · {v.kcal} kcal</span>
            </div>
          ))}
        </div>
      </section>

      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <h2>{titles[mode][0]}</h2>
          {notice && !info && !error && mode === "login" && <div className="notice info" role="status">{notice}</div>}
          {info && <div className="notice ok">{info}</div>}
          {error && <div className="notice error" role="alert">{error}</div>}

          {mode === "register" && (
            <div className="field">
              <label htmlFor="name">Your name</label>
              <input id="name" className="input" value={form.full_name} onChange={set("full_name")} autoComplete="name" maxLength={80} />
            </div>
          )}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" required value={form.email} onChange={set("email")} autoComplete="email" />
          </div>

          {(mode === "login" || mode === "register") && (
            <div className="field">
              <label htmlFor="pw">Password</label>
              <input id="pw" className="input" type="password" required maxLength={128}
                value={form.password} onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"}
                aria-describedby={mode === "register" ? "pw-rules" : undefined} />
              {mode === "register" && <PasswordRules id="pw-rules" pw={form.password} email={form.email} />}
            </div>
          )}

          {mode === "register" && (
            <div className="field">
              <label htmlFor="lang">Language you'll speak in</label>
              <select id="lang" className="select" value={form.lang} onChange={set("lang")}>
                {FALLBACK_LANGS.map((l) => <option key={l.code} value={l.code}>{l.native} ({l.name})</option>)}
              </select>
            </div>
          )}

          {mode === "reset" && (
            <>
              <div className="field">
                <label htmlFor="otp">6-digit code</label>
                <input id="otp" className="input" inputMode="numeric" pattern="\d{6}" maxLength={6} required value={form.otp} onChange={set("otp")} autoComplete="one-time-code" />
              </div>
              <div className="field">
                <label htmlFor="npw">New password</label>
                <input id="npw" className="input" type="password" maxLength={128} required value={form.new_password} onChange={set("new_password")}
                  autoComplete="new-password" aria-describedby="npw-rules" />
                <PasswordRules id="npw-rules" pw={form.new_password} email={form.email} />
              </div>
            </>
          )}

          <button className="btn btn-dark" type="submit" disabled={busy} style={{ width: "100%", padding: "0.85rem" }}>
            {busy ? "Please wait…" : titles[mode][1]}
          </button>

          <div className="small" style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
            {mode === "login" && (
              <>
                <span>New here? <button type="button" className="link-btn" onClick={() => go("register")}>Create an account</button></span>
                <button type="button" className="link-btn" onClick={() => go("forgot")}>Forgot password?</button>
              </>
            )}
            {mode !== "login" && (
              <span>Have an account? <button type="button" className="link-btn" onClick={() => go("login")}>Sign in</button></span>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}

const RULES = ["At least 8 characters", "At least one letter", "At least one number"];

function PasswordRules({ id, pw, email }) {
  const problems = passwordProblems(pw, email);
  return (
    <ul id={id} className="pw-rules" aria-live="polite">
      {RULES.map((r) => (
        <li key={r} className={pw && !problems.includes(r) ? "met" : ""}>{r}</li>
      ))}
      {problems.filter((p) => !RULES.includes(p)).map((p) => <li key={p} className="bad">{p}</li>)}
    </ul>
  );
}
