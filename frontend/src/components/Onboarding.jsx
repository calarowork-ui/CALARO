import { useMemo, useState } from "react";
import { Check, ChevronLeft, Minus, Plus } from "lucide-react";

import { completeOnboarding } from "../api/onboarding";
import { FALLBACK_LANGS, errorText } from "../lib/format";
import { PlanView } from "./PlanView";
import { BrandMark } from "./Shell";

const GOALS = [
  ["lose", "Lose weight", "A steady calorie cut, with more protein so you keep muscle"],
  ["maintain", "Stay where I am", "Calories matched to what your body uses"],
  ["gain", "Gain weight or muscle", "A gentle surplus and the highest protein target"],
  ["blood_sugar", "Control blood sugar", "Fewer carbs, more fibre, and pairing tips for rice and roti"],
  ["eat_better", "Just eat better", "Balanced targets and nudges on sugar, fried food and protein"],
];
const ACTIVITY = [
  ["sedentary", "Mostly sitting", "Desk job or home, little walking"],
  ["light", "On my feet sometimes", "Walks or light exercise 1–3 days a week"],
  ["moderate", "Regular exercise", "3–5 days a week: gym, yoga, sport or brisk walks"],
  ["active", "Very active", "Hard training 6–7 days a week"],
  ["very_active", "Physical work", "Labour-heavy job or training twice a day"],
];
const MEALS = [
  ["early_tea", "Early tea"], ["breakfast", "Breakfast"], ["mid_morning", "Mid-morning"], ["lunch", "Lunch"],
  ["evening_snack", "Evening snack"], ["dinner", "Dinner"], ["late_night", "Late night"],
];
const DIETS = [
  ["vegetarian", "Vegetarian", "Dairy, no egg, meat or fish"],
  ["eggetarian", "Eggetarian", "Vegetarian plus eggs"],
  ["non_vegetarian", "Non-vegetarian", "Chicken, fish, mutton or eggs"],
  ["vegan", "Vegan", "No dairy, no animal products"],
  ["jain", "Jain", "Vegetarian, no root vegetables"],
];
const REGIONS = [
  ["south", "South Indian", "Idli, dosa, rice, sambar"],
  ["north", "North Indian", "Roti, dal, sabzi, paratha"],
  ["east", "East Indian", "Rice, fish, dal, mishti"],
  ["west", "West Indian", "Poha, thepla, bhakri, usal"],
  ["northeast", "North-East", "Rice, steamed and smoked dishes"],
  ["mixed", "A bit of everything", "Home food from many regions"],
];
const FASTING = [["none", "No"], ["weekly", "A day each week"], ["festivals", "During festivals"], ["ramadan", "Ramadan"], ["intermittent", "Intermittent fasting"]];
const CONDITIONS = [
  ["diabetes", "Diabetes"], ["prediabetes", "Prediabetes"], ["high_bp", "High blood pressure"], ["thyroid", "Thyroid"],
  ["pcos", "PCOS / PCOD"], ["cholesterol", "High cholesterol"], ["none", "None of these"],
];
const CHALLENGES = [
  ["sweets", "Sweets and mithai"], ["fried_snacks", "Fried snacks"], ["late_night", "Eating late at night"],
  ["big_portions", "Big portions, second helpings"], ["skipping_meals", "Skipping meals"], ["eating_out", "Eating out or ordering in"],
  ["low_protein", "Not enough protein"],
];

const STEPS = [
  { title: "About you", why: "Age, sex, height and weight set how many calories your body uses at rest." },
  { title: "Your goal", why: "Your goal sets your calorie target, your protein target and a realistic timeline." },
  { title: "Your day", why: "Activity changes your daily needs. Your meal times split the target, and tea and coffee often hide the most sugar." },
  { title: "Your food", why: "These shape protein picks you will actually eat and swaps that fit your usual plate." },
  { title: "Your health", why: "Optional and private. They only change your carb share, fibre and the tips you see." },
];

function Choice({ options, value, onChange, multi = false, cols = 1 }) {
  const isOn = (v) => (multi ? value.includes(v) : value === v);
  const toggle = (v) => {
    if (!multi) return onChange(v);
    if (v === "none") return onChange(value.includes("none") ? [] : ["none"]);
    const next = value.filter((x) => x !== "none");
    onChange(next.includes(v) ? next.filter((x) => x !== v) : [...next, v]);
  };
  return (
    <div className="choices" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }} role={multi ? "group" : "radiogroup"}>
      {options.map(([v, label, hint]) => (
        <button key={v} type="button" className="choice" role={multi ? "checkbox" : "radio"} aria-checked={isOn(v)} onClick={() => toggle(v)}>
          <span className="choice-mark">{isOn(v) && <Check size={14} strokeWidth={3} />}</span>
          <span>
            <span className="choice-label">{label}</span>
            {hint && <span className="choice-hint">{hint}</span>}
          </span>
        </button>
      ))}
    </div>
  );
}

function Stepper({ value, onChange, min, max, step = 1, label, unit }) {
  return (
    <div className="stepper">
      <span className="stepper-label">{label}</span>
      <div className="stepper-ctl">
        <button type="button" aria-label={`Less ${label}`} onClick={() => onChange(Math.max(min, +(value - step).toFixed(1)))}><Minus size={16} /></button>
        <span className="stepper-v">{value}{unit && <small> {unit}</small>}</span>
        <button type="button" aria-label={`More ${label}`} onClick={() => onChange(Math.min(max, +(value + step).toFixed(1)))}><Plus size={16} /></button>
      </div>
    </div>
  );
}

export function Onboarding({ user, previous, languages, onDone, onCancel }) {
  const prev = previous || {};
  const [step, setStep] = useState(0);
  const [a, setA] = useState({
    full_name: user.full_name || "", preferred_language: user.preferred_language || "en",
    age: prev.age ?? user.age ?? "", sex: prev.sex ?? user.sex ?? "", height_cm: prev.height_cm ?? user.height_cm ?? "",
    weight_kg: prev.weight_kg ?? user.weight_kg ?? "", goal: prev.goal ?? "", target_weight_kg: prev.target_weight_kg ?? "",
    pace: prev.pace ?? "steady", activity_level: prev.activity_level ?? user.activity_level ?? "",
    meals: prev.meals ?? ["breakfast", "lunch", "dinner"], tea_cups: prev.tea_cups ?? 2, sugar_spoons: prev.sugar_spoons ?? 1,
    diet: prev.diet ?? "", region: prev.region ?? "", fasting: prev.fasting ?? "none",
    conditions: prev.conditions ?? [], challenge: prev.challenge ?? "",
  });
  const [ftMode, setFtMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const set = (k) => (v) => setA((s) => ({ ...s, [k]: v?.target ? v.target.value : v }));
  const langs = languages?.length ? languages : FALLBACK_LANGS;

  const healthy = useMemo(() => {
    const h = Number(a.height_cm) / 100;
    return h > 1 ? [Math.round(18.5 * h * h), Math.round(22.9 * h * h)] : null;
  }, [a.height_cm]);

  const ft = Math.floor((Number(a.height_cm) || 0) / 30.48);
  const inch = Math.round(((Number(a.height_cm) || 0) - ft * 30.48) / 2.54);
  const setFtIn = (f, i) => set("height_cm")(String(Math.round((Number(f) * 30.48 + Number(i) * 2.54) * 10) / 10));

  const problems = useMemo(() => {
    const p = [];
    if (step === 0) {
      if (!(a.age >= 13 && a.age <= 100)) p.push("Enter an age between 13 and 100.");
      if (!a.sex) p.push("Choose female or male.");
      if (!(a.height_cm >= 120 && a.height_cm <= 220)) p.push("Enter a height between 120 and 220 cm.");
      if (!(a.weight_kg >= 30 && a.weight_kg <= 250)) p.push("Enter a weight between 30 and 250 kg.");
    }
    if (step === 1) {
      if (!a.goal) p.push("Choose a goal.");
      if (a.goal === "lose" && a.target_weight_kg && Number(a.target_weight_kg) >= Number(a.weight_kg)) p.push("Your target should be below your current weight.");
      if (a.goal === "gain" && a.target_weight_kg && Number(a.target_weight_kg) <= Number(a.weight_kg)) p.push("Your target should be above your current weight.");
    }
    if (step === 2) {
      if (!a.activity_level) p.push("Choose how active you are.");
      if (!a.meals.length) p.push("Pick at least one meal.");
    }
    if (step === 3) {
      if (!a.diet) p.push("Choose what you eat.");
      if (!a.region) p.push("Choose the food you eat most.");
    }
    if (step === 4 && !a.challenge) p.push("Choose what's hardest for you.");
    return p;
  }, [a, step]);

  const next = async () => {
    setError("");
    if (problems.length) {
      setError(problems[0]);
      return;
    }
    if (step < STEPS.length - 1) {
      setStep(step + 1);
      window.scrollTo({ top: 0 });
      return;
    }
    setBusy(true);
    try {
      const payload = {
        ...a,
        full_name: a.full_name || null,
        age: Number(a.age), height_cm: Number(a.height_cm), weight_kg: Number(a.weight_kg),
        target_weight_kg: ["lose", "gain"].includes(a.goal) && a.target_weight_kg ? Number(a.target_weight_kg) : null,
        tea_cups: Number(a.tea_cups), sugar_spoons: Number(a.sugar_spoons),
      };
      const res = await completeOnboarding(payload);
      setResult(res);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorText(err, "Your answers couldn't be saved. Try again."));
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <div className="onb onb-plan">
        <header className="onb-top"><div className="brand"><BrandMark /><span className="brand-name">CALARO</span></div></header>
        <main className="onb-plan-main">
          <h1>Your plan is ready</h1>
          <p className="muted" style={{ margin: "0.4rem 0 1.75rem" }}>Built from your answers. Your Today screen now tracks these targets, and you can retake the questions any time from Profile.</p>
          <PlanView plan={result.plan} name={result.user.full_name?.split(" ")[0]} onStart={() => onDone(result.user)} />
        </main>
      </div>
    );
  }

  const s = STEPS[step];
  return (
    <div className="onb">
      <aside className="onb-side">
        <div className="brand"><BrandMark /><span className="brand-name">CALARO</span></div>
        <div>
          <p className="onb-hello">Five quick questions, about two minutes. Your answers turn into a plan made for you, not a generic 2,000 kcal.</p>
          <ol className="onb-steps">
            {STEPS.map((st, i) => (
              <li key={st.title} className={i === step ? "now" : i < step ? "done" : ""}>
                <span className="onb-dot">{i < step ? <Check size={13} strokeWidth={3} /> : i + 1}</span>
                {st.title}
              </li>
            ))}
            <li className=""><span className="onb-dot">✓</span>Your plan</li>
          </ol>
        </div>
        {onCancel && <button className="link-btn" style={{ color: "#b9d1c4" }} onClick={onCancel}>Cancel and keep my current plan</button>}
      </aside>

      <main className="onb-main">
        <div className="onb-progress" aria-hidden="true"><i style={{ width: `${((step + 1) / (STEPS.length + 1)) * 100}%` }} /></div>
        <p className="muted small">Step {step + 1} of {STEPS.length}</p>
        <h1>{s.title}</h1>
        <p className="onb-why">{s.why}</p>

        <div className="onb-body">
          {step === 0 && (
            <>
              <div className="form-grid">
                <div className="field span-2">
                  <label htmlFor="o-name">What should we call you?</label>
                  <input id="o-name" className="input" value={a.full_name} onChange={set("full_name")} autoComplete="given-name" maxLength={80} />
                </div>
                <div className="field span-2">
                  <label>Language you'll speak to CALARO in</label>
                  <div className="lang-pick">
                    {langs.map((l) => (
                      <button key={l.code} type="button" className="pill" aria-pressed={a.preferred_language === l.code} onClick={() => set("preferred_language")(l.code)} lang={l.code}>{l.native}</button>
                    ))}
                  </div>
                </div>
                <div className="field">
                  <label htmlFor="o-age">Age</label>
                  <input id="o-age" className="input" type="number" inputMode="numeric" min="13" max="100" value={a.age} onChange={set("age")} />
                </div>
                <div className="field">
                  <label>Sex</label>
                  <div className="seg" role="group" aria-label="Sex">
                    {[["female", "Female"], ["male", "Male"]].map(([v, l]) => (
                      <button type="button" key={v} aria-pressed={a.sex === v} onClick={() => set("sex")(v)}>{l}</button>
                    ))}
                  </div>
                  <span className="small muted">Used for the energy formula only.</span>
                </div>
                <div className="field">
                  <label htmlFor="o-h">Height <button type="button" className="link-btn small" onClick={() => setFtMode(!ftMode)}>{ftMode ? "use cm" : "use feet and inches"}</button></label>
                  {ftMode ? (
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <input className="input" type="number" min="4" max="7" value={a.height_cm ? ft : ""} onChange={(e) => setFtIn(e.target.value, inch || 0)} aria-label="Feet" placeholder="ft" />
                      <input className="input" type="number" min="0" max="11" value={a.height_cm ? inch : ""} onChange={(e) => setFtIn(ft || 5, e.target.value)} aria-label="Inches" placeholder="in" />
                    </div>
                  ) : (
                    <input id="o-h" className="input" type="number" inputMode="decimal" placeholder="cm" value={a.height_cm} onChange={set("height_cm")} />
                  )}
                </div>
                <div className="field">
                  <label htmlFor="o-w">Weight (kg)</label>
                  <input id="o-w" className="input" type="number" inputMode="decimal" step="0.1" value={a.weight_kg} onChange={set("weight_kg")} />
                  {healthy && <span className="small muted">Healthy for your height: {healthy[0]}–{healthy[1]} kg</span>}
                </div>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <Choice options={GOALS} value={a.goal} onChange={set("goal")} />
              {["lose", "gain"].includes(a.goal) && (
                <div className="onb-sub">
                  <div className="form-grid">
                    <div className="field">
                      <label htmlFor="o-t">Target weight (kg), optional</label>
                      <input id="o-t" className="input" type="number" step="0.5" value={a.target_weight_kg} onChange={set("target_weight_kg")}
                        placeholder={healthy ? (a.goal === "lose" ? `e.g. ${healthy[1]}` : `e.g. ${healthy[0] + 3}`) : ""} />
                    </div>
                  </div>
                  <p className="field-label">How fast?</p>
                  <Choice cols={2} value={a.pace} onChange={set("pace")} options={a.goal === "lose"
                    ? [["gentle", "Gentle", "About 0.25 kg a week, easier to keep up"], ["steady", "Steady", "About 0.5 kg a week, the usual safe rate"]]
                    : [["gentle", "Gentle", "About 0.2 kg a week, less fat gain"], ["steady", "Steady", "About 0.35 kg a week"]]} />
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <Choice options={ACTIVITY} value={a.activity_level} onChange={set("activity_level")} />
              <p className="field-label">Which of these do you usually eat?</p>
              <div className="lang-pick">
                {MEALS.map(([v, l]) => (
                  <button key={v} type="button" className="pill" aria-pressed={a.meals.includes(v)}
                    onClick={() => set("meals")(a.meals.includes(v) ? a.meals.filter((m) => m !== v) : [...a.meals, v])}>{l}</button>
                ))}
              </div>
              <p className="field-label">Tea and coffee</p>
              <div className="steppers">
                <Stepper label="Cups a day" value={a.tea_cups} onChange={set("tea_cups")} min={0} max={12} />
                <Stepper label="Sugar per cup" unit="tsp" value={a.sugar_spoons} onChange={set("sugar_spoons")} min={0} max={6} step={0.5} />
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <Choice options={DIETS} value={a.diet} onChange={set("diet")} cols={2} />
              <p className="field-label">The food you eat most days</p>
              <Choice options={REGIONS} value={a.region} onChange={set("region")} cols={2} />
              <p className="field-label">Do you fast?</p>
              <div className="lang-pick">
                {FASTING.map(([v, l]) => (
                  <button key={v} type="button" className="pill" aria-pressed={a.fasting === v} onClick={() => set("fasting")(v)}>{l}</button>
                ))}
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <p className="field-label" style={{ marginTop: 0 }}>Has a doctor told you that you have any of these?</p>
              <Choice options={CONDITIONS} value={a.conditions} onChange={set("conditions")} multi cols={2} />
              <p className="field-label">What's hardest for you right now?</p>
              <Choice options={CHALLENGES} value={a.challenge} onChange={set("challenge")} cols={2} />
            </>
          )}
        </div>

        {error && <div className="notice error" role="alert" style={{ marginTop: "1.25rem" }}>{error}</div>}

        <div className="onb-nav">
          {step > 0 ? (
            <button type="button" className="btn btn-ghost" onClick={() => { setError(""); setStep(step - 1); }}><ChevronLeft size={16} /> Back</button>
          ) : <span />}
          <button type="button" className="btn btn-dark" onClick={next} disabled={busy}>
            {busy ? "Building your plan…" : step === STEPS.length - 1 ? "See my plan" : "Continue"}
          </button>
        </div>
      </main>
    </div>
  );
}
