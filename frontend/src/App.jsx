import { useCallback, useEffect, useState } from "react";

import { fetchMe, loginUser, registerUser, updateProfile } from "./api/auth";
import { fetchVaaniStatus } from "./api/vaani";
import { endMonitoring } from "./api/admin";
import { AuthView } from "./components/AuthView";
import { Onboarding } from "./components/Onboarding";
import { Shell } from "./components/Shell";
import { AdminPage } from "./pages/AdminPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ProfilePage } from "./pages/ProfilePage";
import { TeamPage } from "./pages/TeamPage";
import { TodayPage } from "./pages/TodayPage";
import { FALLBACK_LANGS } from "./lib/format";
import { ADMIN_IDLE_MINUTES, IDLE_MINUTES, effectiveIdleMinutes, useIdleSignOut } from "./lib/session";

function storedToken() {
  try {
    return localStorage.getItem("calaro_token");
  } catch {
    return null;
  }
}

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [page, setPage] = useState("today");
  const [vaani, setVaani] = useState({ bhashini_configured: false, languages: FALLBACK_LANGS });
  const [notice, setNotice] = useState("");

  const signOut = useCallback(async (reason) => {
    setNotice(typeof reason === "string" ? reason : "");
    // close the Grafana session first so a shared computer can't reopen it
    await Promise.race([endMonitoring(), new Promise((r) => setTimeout(r, 1500))]);
    try {
      localStorage.removeItem("calaro_token");
    } catch {
      /* ignore */
    }
    setUser(null);
    setPage("today");
  }, []);

  useEffect(() => {
    fetchVaaniStatus().then(setVaani).catch(() => {});
    const expired = () => signOut("Your session ended. Sign in again to continue.");
    window.addEventListener("calaro:signed-out", expired);
    (async () => {
      if (storedToken()) {
        try {
          setUser(await fetchMe());
        } catch {
          signOut();
        }
      }
      setBooting(false);
    })();
    return () => window.removeEventListener("calaro:signed-out", expired);
  }, [signOut]);

  const handleAuth = async (mode, form) => {
    if (mode === "register") {
      await registerUser({ email: form.email, password: form.password, full_name: form.full_name || null, preferred_language: form.lang });
    }
    const { access_token } = await loginUser({ email: form.email, password: form.password });
    localStorage.setItem("calaro_token", access_token);
    setUser(await fetchMe());
    setNotice("");
    setPage("today");
  };

  const idleMinutes = effectiveIdleMinutes(user?.is_admin ? ADMIN_IDLE_MINUTES : IDLE_MINUTES);
  const onIdle = useCallback(
    () => signOut(`You were signed out after ${idleMinutes} minute${idleMinutes === 1 ? "" : "s"} without activity, to keep your account safe.`),
    [signOut, idleMinutes]
  );
  useIdleSignOut(Boolean(user), idleMinutes, onIdle);

  const changeLanguage = (code) => {
    setUser((u) => ({ ...u, preferred_language: code }));
    updateProfile({ preferred_language: code }).catch(() => {});
  };

  if (booting) return <div className="loading">Opening CALARO…</div>;
  if (!user) return <AuthView onAuthenticated={handleAuth} notice={notice} />;

  const lang = user.preferred_language || "en";
  const languages = vaani.languages?.length ? vaani.languages : FALLBACK_LANGS;

  if (user.needs_onboarding) {
    return <Onboarding user={user} languages={languages} onDone={(u) => { setUser(u); setPage("today"); }} />;
  }
  const allowed = page === "admin" ? user.is_admin : page === "team" ? user.is_superadmin : true;
  const current = allowed ? page : "today";

  return (
    <Shell user={user} page={current} onNavigate={setPage} onSignOut={signOut}>
      {current === "today" && (
        <TodayPage user={user} lang={lang} languages={languages} voiceReady={vaani.bhashini_configured}
          onLanguageChange={changeLanguage} onNavigate={setPage} />
      )}
      {current === "history" && <HistoryPage user={user} />}
      {current === "profile" && (
        <ProfilePage user={user} languages={languages} onUserChange={(patch) => setUser((u) => ({ ...u, ...patch }))}
          onUserReplace={setUser} />
      )}
      {current === "admin" && <AdminPage user={user} />}
      {current === "team" && <TeamPage user={user} />}
    </Shell>
  );
}
