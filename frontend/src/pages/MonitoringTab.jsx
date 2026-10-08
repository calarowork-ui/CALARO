import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";

import { startMonitoring } from "../api/admin";
import { errorText } from "../lib/format";

const VIEWS = [
  ["overview", "Traffic & usage"],
  ["logs", "Logs"],
  ["server", "Server health"],
];
const RANGES = [["now-1h", "1 h"], ["now-6h", "6 h"], ["now-24h", "24 h"], ["now-7d", "7 days"], ["now-30d", "30 days"]];

export function MonitoringTab() {
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("overview");
  const [range, setRange] = useState("now-24h");
  const [reloadKey, setReloadKey] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    startMonitoring()
      .then(setSession)
      .catch((e) => setError(errorText(e, "Monitoring couldn't start. Check that you're signed in as an admin.")));
  }, []);

  const base = session?.dashboards?.[view];
  const src = useMemo(() => {
    if (!base) return null;
    const q = new URLSearchParams({ orgId: "1", theme: "light", from: range, to: "now", refresh: "30s" });
    // the Logs view keeps Grafana's filter bar (service, search); the others go full-bleed
    return `${base}?${q.toString()}${view === "logs" ? "" : "&kiosk"}`;
  }, [base, range, view]);

  useEffect(() => setLoaded(false), [src, reloadKey]);

  if (error) return <div className="notice error">{error}</div>;

  return (
    <div className="monitoring">
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div className="seg" role="group" aria-label="Dashboard">
          {VIEWS.map(([id, label]) => (
            <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <div className="seg" role="group" aria-label="Time range">
            {RANGES.map(([v, label]) => (
              <button key={v} type="button" aria-pressed={range === v} onClick={() => setRange(v)}>{label}</button>
            ))}
          </div>
          <button className="icon-btn" onClick={() => setReloadKey((k) => k + 1)} aria-label="Reload dashboard"><RefreshCw size={16} /></button>
          {base && (
            <a className="btn btn-ghost btn-sm" href={`${base}?orgId=1&from=${range}&to=now`} target="_blank" rel="noreferrer">
              Open in Grafana <ExternalLink size={14} />
            </a>
          )}
        </div>
      </div>

      <div className="grafana-frame">
        {!loaded && <p className="grafana-loading muted">Loading Grafana…</p>}
        {src && (
          <iframe key={`${src}-${reloadKey}`} title={`Grafana: ${view}`} src={src} onLoad={() => setLoaded(true)}
            referrerPolicy="same-origin" />
        )}
      </div>
      <p className="small muted" style={{ marginTop: "0.6rem" }}>
        Updates every 30 seconds. Logs are kept for 14 days and metrics for 30 days. If this stays blank, Grafana isn't running: it
        starts with <code>docker compose up</code>, not with <code>npm run dev</code>.
      </p>
    </div>
  );
}
