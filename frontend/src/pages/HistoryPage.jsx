import { useEffect, useMemo, useState } from "react";

import { fetchFoodLogs } from "../api/food";
import { fetchProfile } from "../api/auth";
import { dayKey, fmtN, mealLabel, timeOf, toDate } from "../lib/format";

export function HistoryPage() {
  const [logs, setLogs] = useState(null);
  const [goal, setGoal] = useState(null);

  useEffect(() => {
    fetchFoodLogs().then(setLogs).catch(() => setLogs([]));
    fetchProfile().then((p) => setGoal(p.tdee)).catch(() => {});
  }, []);

  const { days, groups, max } = useMemo(() => {
    const byDay = new Map();
    (logs || []).forEach((l) => {
      const k = dayKey(toDate(l.created_at));
      if (!byDay.has(k)) byDay.set(k, []);
      byDay.get(k).push(l);
    });
    const out = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const k = dayKey(d);
      const kcal = (byDay.get(k) || []).reduce((s, l) => s + (l.total_calories || 0), 0);
      out.push({ k, d, kcal, isToday: i === 0 });
    }
    const m = Math.max(goal || 0, ...out.map((o) => o.kcal), 1) * 1.1;
    return { days: out, groups: [...byDay.entries()], max: m };
  }, [logs, goal]);

  const logged = days.filter((d) => d.kcal > 0);
  const avg = logged.length ? logged.reduce((s, d) => s + d.kcal, 0) / logged.length : 0;

  return (
    <>
      <header className="page-head">
        <div>
          <h1>History</h1>
          <p>The last two weeks, day by day.</p>
        </div>
      </header>

      <section className="sheet">
        <div className="sheet-head">
          <h2>Calories per day</h2>
          <span className="muted small">
            {logged.length ? `Average ${fmtN(avg)} kcal on the ${logged.length} day${logged.length === 1 ? "" : "s"} you logged` : "No meals in the last 14 days"}
          </span>
        </div>
        <div className="week" role="img" aria-label="Calories eaten per day for the last 14 days">
          {goal ? <div className="week-goal" style={{ bottom: `${(goal / max) * 100}%` }}><span>Goal {fmtN(goal)}</span></div> : null}
          {days.map((d) => (
            <div key={d.k} className={`bar ${d.isToday ? "today" : ""} ${goal && d.kcal > goal ? "over" : ""}`} title={`${d.d.toDateString()}: ${fmtN(d.kcal)} kcal`}>
              <i style={{ height: `${(d.kcal / max) * 100}%` }} />
              <small>{d.d.toLocaleDateString("en-IN", { weekday: "narrow" })}</small>
            </div>
          ))}
        </div>
      </section>

      {logs === null ? (
        <p className="muted section">Loading your meals…</p>
      ) : groups.length === 0 ? (
        <div className="empty section"><strong>No meals yet</strong>Meals you save on the Today page appear here.</div>
      ) : (
        groups.map(([k, meals]) => {
          const d = toDate(meals[0].created_at);
          const total = meals.reduce((s, l) => s + (l.total_calories || 0), 0);
          return (
            <section className="day-group" key={k}>
              <div className="day-head">
                <h3>{d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}</h3>
                <span className="num">{fmtN(total)} kcal</span>
              </div>
              <ul className="ledger">
                {meals.map((m) => (
                  <li className="ledger-item" key={m.id} style={{ gridTemplateColumns: "64px minmax(0,1fr) auto" }}>
                    <span className="ledger-time">{timeOf(m.created_at)}<br /><span className="small">{mealLabel(m.created_at)}</span></span>
                    <div className="ledger-text">
                      <div className="native" lang={m.language || "en"}>{m.native_text || m.raw_text}</div>
                      <div className="foods">{m.items.map((i) => `${i.quantity} ${i.name.split(" / ")[0]}`).join(", ")}</div>
                    </div>
                    <div className="ledger-kcal">{fmtN(m.total_calories)}<span>{Math.round(m.total_protein || 0)} g protein</span></div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })
      )}
    </>
  );
}
