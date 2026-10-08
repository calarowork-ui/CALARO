import { useCallback, useEffect, useState } from "react";

import { createAdmin, fetchAdmins, fetchAudit, revokeAdmin } from "../api/admin";
import { errorText, toDate } from "../lib/format";

const ACTION_TEXT = {
  admin_created: "created admin",
  admin_promoted: "made admin",
  admin_revoked: "removed admin rights from",
  user_deactivated: "deactivated",
  user_activated: "reactivated",
};

export function TeamPage() {
  const [admins, setAdmins] = useState([]);
  const [audit, setAudit] = useState([]);
  const [form, setForm] = useState({ email: "", full_name: "", password: "" });
  const [state, setState] = useState({ busy: false, err: "", msg: "" });

  const load = useCallback(() => {
    fetchAdmins().then(setAdmins).catch((e) => setState((s) => ({ ...s, err: errorText(e, "Couldn't load admins.") })));
    fetchAudit().then(setAudit).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true, err: "", msg: "" });
    try {
      const a = await createAdmin({ email: form.email, full_name: form.full_name || null, password: form.password || null });
      setState({ busy: false, err: "", msg: `${a.email} is now an admin.${form.password ? " Share the temporary password with them privately." : ""}` });
      setForm({ email: "", full_name: "", password: "" });
      load();
    } catch (err) {
      setState({ busy: false, err: errorText(err, "Couldn't add this admin."), msg: "" });
    }
  };

  const revoke = async (a) => {
    if (!window.confirm(`Remove admin rights from ${a.email}? Their account stays as a normal member.`)) return;
    try {
      await revokeAdmin(a.id);
      setState({ busy: false, err: "", msg: `${a.email} is no longer an admin.` });
      load();
    } catch (err) {
      setState({ busy: false, err: errorText(err, "Couldn't remove this admin."), msg: "" });
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Admin team</h1>
          <p>Only you, the super-admin, can see this page, add admins or remove them.</p>
        </div>
      </header>

      {state.err && <div className="notice error" style={{ marginBottom: "1rem" }}>{state.err}</div>}
      {state.msg && <div className="notice ok" style={{ marginBottom: "1rem" }}>{state.msg}</div>}

      <div className="team-grid">
        <section>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Last sign-in</th><th /></tr></thead>
              <tbody>
                {admins.map((a) => (
                  <tr key={a.id}>
                    <td>{a.full_name || "—"}</td>
                    <td>{a.email}</td>
                    <td><span className={`role ${a.role}`}>{a.role === "superadmin" ? "super-admin" : "admin"}</span></td>
                    <td>{a.last_login_at ? toDate(a.last_login_at).toLocaleDateString("en-IN") : "Never"}</td>
                    <td className="r">
                      {a.role !== "superadmin" && <button className="btn btn-sm btn-danger" onClick={() => revoke(a)}>Remove admin</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="sheet" style={{ marginTop: "1.25rem" }}>
            <div className="sheet-head"><h2>Recent changes</h2></div>
            {audit.length === 0 ? <p className="muted small">No changes yet.</p> : (
              <ul className="audit">
                {audit.map((e, i) => (
                  <li key={i}>
                    <strong>{e.actor_email}</strong> {ACTION_TEXT[e.action] || e.action} <strong>{e.target_email}</strong>
                    <span className="muted small"> · {toDate(e.at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <form className="sheet" onSubmit={submit}>
          <h2>Add an admin</h2>
          <p className="muted small" style={{ margin: "0.4rem 0 1rem" }}>
            If the email already has a CALARO account, it's upgraded to admin and the password is left as it is.
            Otherwise a new admin account is created with the temporary password you set.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.9rem" }}>
            <div className="field">
              <label htmlFor="ae">Email</label>
              <input id="ae" className="input" type="email" required value={form.email} onChange={set("email")} />
            </div>
            <div className="field">
              <label htmlFor="an">Name</label>
              <input id="an" className="input" value={form.full_name} onChange={set("full_name")} />
            </div>
            <div className="field">
              <label htmlFor="ap">Temporary password</label>
              <input id="ap" className="input" type="text" minLength={8} value={form.password} onChange={set("password")} autoComplete="off"
                placeholder="Only needed for a new account" />
            </div>
            <button className="btn btn-dark" disabled={state.busy}>{state.busy ? "Adding…" : "Add admin"}</button>
          </div>
        </form>
      </div>
    </>
  );
}
