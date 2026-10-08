import { useCallback, useEffect, useMemo, useState } from "react";
import { Flame, Trash2 } from "lucide-react";

import { deleteFoodLog, fetchFoodLogs } from "../api/food";
import { fetchProfile } from "../api/auth";
import { fetchToday } from "../api/vaani";
import { Thali, ThaliLegend, targetsFor } from "../components/Thali";
import { VaaniLogger } from "../components/VaaniLogger";
import { dayKey, fmtN, greeting, mealLabel, timeOf, toDate } from "../lib/format";

export function TodayPage({ user, lang, languages, voiceReady, onLanguageChange, onNavigate }) {
  const [today, setToday] = useState(null);
  const [profile, setProfile] = useState(null);
  const [logs, setLogs] = useState([]);

  const load = useCallback(async () => {
    const [t, p, l] = await Promise.allSettled([fetchToday(), fetchProfile(), fetchFoodLogs()]);
    if (t.status === "fulfilled") setToday(t.value);
    if (p.status === "fulfilled") setProfile(p.value);
    if (l.status === "fulfilled") setLogs(l.value);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const todaysMeals = useMemo(() => {
    const k = dayKey(new Date());
    return logs.filter((l) => dayKey(toDate(l.created_at)) === k);
  }, [logs]);

  const targets = today?.targets?.calories
    ? { ...targetsFor(today.targets.calories, profile?.weight_kg), ...today.targets }
    : targetsFor(today?.goal ?? profile?.tdee, profile?.weight_kg ?? user.weight_kg);
  const first = (user.full_name || "").split(" ")[0];
  const dateLine = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

  const remove = async (id) => {
    setLogs((prev) => prev.filter((l) => l.id !== id));
    try {
      await deleteFoodLog(id);
    } finally {
      load();
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <h1>{greeting()}{first ? `, ${first}` : ""}</h1>
          <p>{dateLine}</p>
        </div>
        {today?.streak > 0 && (
          <span className="streak"><Flame size={17} /> {today.streak}-day logging streak</span>
        )}
      </header>

      <div className="today-grid">
        <div className="thali-col">
          <Thali totals={today?.totals} targets={targets} />
          <div>
            <ThaliLegend totals={today?.totals} targets={targets} />
            {!targets.calories && (
              <p className="goal-cta small" style={{ marginTop: "1rem" }}>
                Add your age, height and weight to get a daily calorie goal.{" "}
                <button className="link-btn" onClick={() => onNavigate("profile")}>Set my goal</button>
              </p>
            )}
          </div>
        </div>

        <div>
          <VaaniLogger lang={lang} languages={languages} voiceReady={voiceReady} onLanguageChange={onLanguageChange}
            onSaved={(log) => { setLogs((p) => [log, ...p]); load(); }} />

          <section className="section">
            <div className="sheet-head">
              <h2>Today's meals</h2>
              {todaysMeals.length > 0 && <span className="muted small">{todaysMeals.length} logged</span>}
            </div>
            {todaysMeals.length === 0 ? (
              <div className="empty">
                <strong>Nothing on the plate yet</strong>
                Speak or type your first meal above. It will show up here.
              </div>
            ) : (
              <ul className="ledger">
                {todaysMeals.map((m) => (
                  <li className="ledger-item" key={m.id}>
                    <span className="ledger-time">{timeOf(m.created_at)}<br /><span className="small">{mealLabel(m.created_at)}</span></span>
                    <div className="ledger-text">
                      <div className="native" lang={m.language || "en"}>{m.native_text || m.raw_text}</div>
                      <div className="foods">{m.items.map((i) => `${i.quantity} ${i.name.split(" / ")[0]}`).join(", ")}</div>
                    </div>
                    <div className="ledger-kcal">{fmtN(m.total_calories)}<span>{Math.round(m.total_protein || 0)} g protein</span></div>
                    <button className="remove" aria-label="Delete this meal" onClick={() => remove(m.id)}><Trash2 size={16} /></button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
