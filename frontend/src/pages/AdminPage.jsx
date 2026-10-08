import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fetchAllLogs, fetchOverview, fetchUsers, setUserActive } from "../api/admin";
import { errorText, fmtN, langName, timeOf, toDate } from "../lib/format";
import { MonitoringTab } from "./MonitoringTab";

function BarsList({ rows, label }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (!rows.length) return <p className="muted small">No data yet.</p>;
  return (
    <ul className="bars-list" aria-label={label}>
      {rows.map((r) => (
        <li key={r.name}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.name}</span>
          <span className="track"><i style={{ width: `${(r.count / max) * 100}%` }} /></span>
          <span className="c">{r.count}</span>
        </li>
      ))}
    </ul>
  );
}

function Overview() {
  const [o, setO] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    fetchOverview().then(setO).catch((e) => setErr(errorText(e, "Couldn't load the overview.")));
  }, []);
  if (err) return <div className="notice error">{err}</div>;
  if (!o) return <p className="muted">Loading…</p>;
  const chart = o.daily.map((d) => ({ ...d, label: new Date(d.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) }));
  return (
    <>
      <div className="kpis">
        <div className="kpi"><span className="muted small">People</span><div className="v">{fmtN(o.total_users)}</div><span className="d">{o.new_users_7d} joined this week</span></div>
        <div className="kpi"><span className="muted small">Logged this week</span><div className="v">{fmtN(o.active_users_7d)}</div><span className="d">people with at least one meal</span></div>
        <div className="kpi"><span className="muted small">Meals saved</span><div className="v">{fmtN(o.total_meals)}</div><span className="d">{o.meals_today} today</span></div>
        <div className="kpi"><span className="muted small">Average meal</span><div className="v">{fmtN(o.avg_calories_per_meal)}</div><span className="d">kcal</span></div>
      </div>
      <div className="admin-grid">
        <section className="sheet">
          <div className="sheet-head"><h2>Meals per day</h2><span className="muted small">Last 14 days</span></div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
                <CartesianGrid vertical={false} stroke="#e3e8e5" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#66746d" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#66746d" }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: "#eef1ef" }} contentStyle={{ borderRadius: 10, border: "1px solid #d6ddd9" }}
                  formatter={(v, n) => [v, n === "meals" ? "Meals" : "People"]} />
                <Bar dataKey="meals" fill="#1f6a4f" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="sheet">
          <div className="sheet-head"><h2>Languages used</h2><span className="muted small">14 days</span></div>
          <BarsList label="Languages" rows={o.languages.map((l) => ({ name: langName(l.name), count: l.count }))} />
          <div className="sheet-head" style={{ marginTop: "1.5rem" }}><h2>Most logged dishes</h2></div>
          <BarsList label="Dishes" rows={o.top_foods} />
        </section>
      </div>
    </>
  );
}

function Users({ me }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const t = setTimeout(() => fetchUsers(q).then(setRows).catch((e) => setErr(errorText(e, "Couldn't load people."))), 250);
    return () => clearTimeout(t);
  }, [q]);

  const toggle = async (u) => {
    setErr("");
    try {
      const updated = await setUserActive(u.id, !u.is_active);
      setRows((rs) => rs.map((r) => (r.id === u.id ? { ...r, ...updated } : r)));
    } catch (e) {
      setErr(errorText(e, "Couldn't change this account."));
    }
  };

  return (
    <>
      <div className="toolbar">
        <input className="input" placeholder="Search by name or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search people" />
        {rows && <span className="muted small">{rows.length} shown</span>}
      </div>
      {err && <div className="notice error" style={{ marginBottom: "1rem" }}>{err}</div>}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Language</th><th className="r">Meals</th><th>Joined</th><th>Last sign-in</th><th /></tr>
          </thead>
          <tbody>
            {(rows || []).map((u) => (
              <tr key={u.id}>
                <td>{u.full_name || "—"}</td>
                <td>{u.email}</td>
                <td><span className={`role ${u.is_active ? u.role : "off"}`}>{u.is_active ? u.role : "deactivated"}</span></td>
                <td>{langName(u.preferred_language)}</td>
                <td className="r">{u.meals}</td>
                <td>{toDate(u.created_at)?.toLocaleDateString("en-IN")}</td>
                <td>{u.last_login_at ? toDate(u.last_login_at).toLocaleDateString("en-IN") : "Never"}</td>
                <td className="r">
                  {u.role === "user" && u.id !== me.id && (
                    <button className={`btn btn-sm ${u.is_active ? "btn-danger" : "btn-ghost"}`} onClick={() => toggle(u)}>
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td colSpan={8} className="muted">No one matches that search.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}

function RecentMeals() {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    fetchAllLogs().then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>When</th><th>Person</th><th>What they said</th><th>Language</th><th className="r">kcal</th></tr></thead>
        <tbody>
          {(rows || []).map((l) => (
            <tr key={l.id}>
              <td style={{ whiteSpace: "nowrap" }}>{toDate(l.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}, {timeOf(l.created_at)}</td>
              <td>{l.user_email || "—"}</td>
              <td lang={l.language || "en"}>{l.native_text || l.raw_text}</td>
              <td>{langName(l.language)}</td>
              <td className="r">{fmtN(l.total_calories)}</td>
            </tr>
          ))}
          {rows && rows.length === 0 && <tr><td colSpan={5} className="muted">No meals saved yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export function AdminPage({ user }) {
  const [tab, setTab] = useState("overview");
  const tabs = [["overview", "Overview"], ["monitoring", "Monitoring"], ["users", "People"], ["meals", "Recent meals"]];
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Admin console</h1>
          <p>How CALARO is being used, and who is using it.</p>
        </div>
      </header>
      <div className="subtabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {tab === "overview" && <Overview />}
      {tab === "monitoring" && <MonitoringTab />}
      {tab === "users" && <Users me={user} />}
      {tab === "meals" && <RecentMeals />}
    </>
  );
}
