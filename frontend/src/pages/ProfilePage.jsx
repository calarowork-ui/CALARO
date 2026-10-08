import { useEffect, useState } from "react";

import { fetchProfile, updateProfile } from "../api/auth";
import { fetchPlan } from "../api/onboarding";
import { Onboarding } from "../components/Onboarding";
import { PlanView } from "../components/PlanView";
import { errorText, fmtN } from "../lib/format";

const ACTIVITY = [
  ["sedentary", "Mostly sitting", "Desk work, little walking"],
  ["light", "Lightly active", "Walks or light exercise 1–3 days a week"],
  ["moderate", "Moderately active", "Exercise 3–5 days a week"],
  ["active", "Very active", "Hard exercise 6–7 days a week"],
  ["very_active", "Athlete or physical job", "Training twice a day or labour-heavy work"],
];

export function ProfilePage({ user, languages, onUserChange, onUserReplace }) {
  const [planData, setPlanData] = useState(null);
  const [retake, setRetake] = useState(false);
  useEffect(() => {
    fetchPlan().then(setPlanData).catch(() => setPlanData(null));
  }, [retake]);
  const [form, setForm] = useState({ age: "", sex: "", height_cm: "", weight_kg: "", activity_level: "light", preferred_language: user.preferred_language || "en" });
  const [goal, setGoal] = useState(null);
  const [state, setState] = useState({ busy: false, msg: "", err: "" });

  useEffect(() => {
    fetchProfile().then((p) => {
      setGoal(p.tdee);
      setForm({
        age: p.age ?? "", sex: p.sex ?? "", height_cm: p.height_cm ?? "", weight_kg: p.weight_kg ?? "",
        activity_level: p.activity_level || "light", preferred_language: p.preferred_language || user.preferred_language || "en",
      });
    }).catch(() => {});
  }, [user.preferred_language]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async (e) => {
    e.preventDefault();
    setState({ busy: true, msg: "", err: "" });
    try {
      const p = await updateProfile({
        age: form.age ? Number(form.age) : null,
        height_cm: form.height_cm ? Number(form.height_cm) : null,
        weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
        sex: form.sex || null,
        activity_level: form.activity_level || null,
        preferred_language: form.preferred_language,
      });
      setGoal(p.tdee);
      onUserChange?.({ preferred_language: p.preferred_language, weight_kg: p.weight_kg });
      fetchPlan().then(setPlanData).catch(() => {});
      setState({ busy: false, msg: p.tdee ? "Saved. Your daily goal is updated." : "Saved. Add age, sex, height and weight to get a goal.", err: "" });
    } catch (err) {
      setState({ busy: false, msg: "", err: errorText(err, "Couldn't save. Check the numbers and try again.") });
    }
  };

  if (retake) {
    return (
      <div className="onb-overlay">
        <Onboarding user={user} previous={planData?.answers} languages={languages}
          onCancel={() => setRetake(false)}
          onDone={(u) => { onUserReplace?.(u); setRetake(false); }} />
      </div>
    );
  }

  const w = Number(form.weight_kg) || null;
  const activity = ACTIVITY.find((a) => a[0] === form.activity_level);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Profile & goal</h1>
          <p>Your goal is worked out from your body and how active you are, using the Mifflin-St Jeor formula.</p>
        </div>
        <button className="btn btn-ghost" onClick={() => setRetake(true)}>{planData?.plan ? "Retake the setup questions" : "Answer the setup questions"}</button>
      </header>

      <div className="profile-grid">
        <form className="sheet" onSubmit={save}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="age">Age</label>
              <input id="age" className="input" type="number" min="10" max="110" value={form.age} onChange={set("age")} />
            </div>
            <div className="field">
              <label>Sex</label>
              <div className="seg" role="group" aria-label="Sex">
                {[["female", "Female"], ["male", "Male"]].map(([v, l]) => (
                  <button type="button" key={v} aria-pressed={form.sex === v} onClick={() => setForm((f) => ({ ...f, sex: v }))}>{l}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <label htmlFor="h">Height (cm)</label>
              <input id="h" className="input" type="number" min="80" max="250" value={form.height_cm} onChange={set("height_cm")} />
            </div>
            <div className="field">
              <label htmlFor="w">Weight (kg)</label>
              <input id="w" className="input" type="number" min="20" max="300" step="0.1" value={form.weight_kg} onChange={set("weight_kg")} />
            </div>
            <div className="field span-2">
              <label htmlFor="act">How active are you?</label>
              <select id="act" className="select" value={form.activity_level} onChange={set("activity_level")}>
                {ACTIVITY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              {activity && <span className="small muted">{activity[2]}</span>}
            </div>
            <div className="field span-2">
              <label htmlFor="pl">Language you speak to CALARO in</label>
              <select id="pl" className="select" value={form.preferred_language} onChange={set("preferred_language")}>
                {languages.map((l) => <option key={l.code} value={l.code}>{l.native} ({l.name})</option>)}
              </select>
            </div>
          </div>
          {state.err && <div className="notice error" style={{ marginTop: "1rem" }}>{state.err}</div>}
          {state.msg && <div className="notice ok" style={{ marginTop: "1rem" }}>{state.msg}</div>}
          <div style={{ marginTop: "1.25rem" }}>
            <button className="btn btn-dark" disabled={state.busy}>{state.busy ? "Saving…" : "Save profile"}</button>
          </div>
        </form>

        <aside className="goal-card">
          <p style={{ color: "#a3c4b4" }}>Daily calorie goal</p>
          <p className="goal">{goal ? fmtN(goal) : "Not set"}</p>
          <p style={{ color: "#b9d1c4" }}>{goal ? (planData?.plan ? "kcal a day, set by your plan." : "kcal a day to stay at your current weight.") : "Fill in age, sex, height and weight."}</p>
          {goal ? (
            <dl>
              <dt>Protein</dt><dd>{planData?.plan?.targets.protein ?? Math.round(w ? w * 0.8 : 50)} g</dd>
              <dt>Carbs</dt><dd>{planData?.plan?.targets.carbs ?? Math.round((goal * 0.5) / 4)} g</dd>
              <dt>Fat</dt><dd>{planData?.plan?.targets.fat ?? Math.round((goal * 0.3) / 9)} g</dd>
              <dt>Fibre</dt><dd>{planData?.plan?.targets.fibre ?? 30} g</dd>
            </dl>
          ) : null}
          {planData?.plan && <p className="small" style={{ color: "#b9d1c4", marginTop: "1rem" }}>Set from your plan. Goal: {planData.plan.summary.goal.replace("_", " ")}.</p>}
          <p className="small" style={{ color: "#a3c4b4", marginTop: "1.25rem" }}>
            This is a general estimate, not medical advice. If you have diabetes, kidney disease or are pregnant, ask your doctor for your targets.
          </p>
        </aside>
      </div>

      {planData?.plan && (
        <section className="section">
          <h2 style={{ marginBottom: "1rem" }}>Your plan</h2>
          <PlanView plan={planData.plan} />
        </section>
      )}
    </>
  );
}
