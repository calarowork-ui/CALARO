import { fmtN } from "../lib/format";

const MACROS = [
  ["protein", "Protein", "var(--protein)"],
  ["carbs", "Carbs", "var(--carbs)"],
  ["fat", "Fat", "var(--fat)"],
  ["fibre", "Fibre", "var(--fibre)"],
];
const MEAL_COLORS = ["#0f3d2e", "#1f6a4f", "#e8a317", "#9c5a1e", "#e07b39", "#3e7d4f", "#66746d"];
const GOAL_LINE = {
  lose: "to lose weight steadily",
  gain: "to gain weight steadily",
  maintain: "to stay at your current weight",
  blood_sugar: "with carbs kept to 40% to help steady blood sugar",
  eat_better: "to stay at your current weight while eating better",
};

function BmiScale({ bmi, category }) {
  const lo = 15, hi = 35;
  const pos = Math.min(100, Math.max(0, ((bmi - lo) / (hi - lo)) * 100));
  const seg = (a, b) => `${((b - a) / (hi - lo)) * 100}%`;
  return (
    <div className="bmi">
      <div className="bmi-bar" role="img" aria-label={`BMI ${bmi}, ${category}`}>
        <span style={{ width: seg(15, 18.5), background: "#9fb8c9" }} />
        <span style={{ width: seg(18.5, 23), background: "#3e7d4f" }} />
        <span style={{ width: seg(23, 25), background: "#e8a317" }} />
        <span style={{ width: seg(25, 35), background: "#c8372d" }} />
        <i style={{ left: `${pos}%` }} />
      </div>
      <div className="bmi-ticks"><span>18.5</span><span>23</span><span>25</span></div>
    </div>
  );
}

export function PlanView({ plan, name, onStart, startLabel = "Start logging meals" }) {
  if (!plan) return null;
  const t = plan.targets;
  const totalMeal = plan.meals.reduce((s, m) => s + m.calories, 0) || 1;
  const goal = plan.summary?.goal;
  return (
    <div className="plan">
      <section className="plan-hero">
        <div>
          <p className="plan-kicker">{name ? `${name}, your` : "Your"} daily target</p>
          <p className="plan-kcal">{fmtN(t.calories)} <span>kcal</span></p>
          <p className="plan-why">
            Your body uses about {fmtN(plan.tdee)} kcal a day. This target is set {GOAL_LINE[goal] || ""}
            {plan.calorie_adjustment ? `, ${plan.calorie_adjustment > 0 ? "+" : "−"}${fmtN(Math.abs(plan.calorie_adjustment))} kcal from that.` : "."}
          </p>
        </div>
        <ul className="plan-macros">
          {MACROS.map(([k, label, color]) => (
            <li key={k}>
              <span className="legend-dot" style={{ background: color }} />
              <span>{label}</span>
              <b>{t[k]} g</b>
            </li>
          ))}
          <li><span className="legend-dot" style={{ background: "#c3ccc7" }} /><span>Added sugar, at most</span><b>{t.added_sugar_g} g</b></li>
          <li><span className="legend-dot" style={{ background: "#9fb8c9" }} /><span>Water</span><b>{(t.water_ml / 1000).toFixed(1)} L</b></li>
        </ul>
      </section>

      <div className="plan-grid">
        <section className="sheet">
          <h3>Body</h3>
          <p className="plan-big">BMI {plan.bmi} <span className={`chip ${plan.bmi_category}`}>{plan.bmi_category}</span></p>
          <BmiScale bmi={plan.bmi} category={plan.bmi_category} />
          <p className="small muted" style={{ marginTop: "0.6rem" }}>
            Healthy weight for your height: {plan.healthy_weight_kg[0]}–{plan.healthy_weight_kg[1]} kg (Indian cut-offs).
          </p>
        </section>

        <section className="sheet">
          <h3>Your meals</h3>
          <div className="meal-split" role="img" aria-label="Calories per meal">
            {plan.meals.map((m, i) => (
              <span key={m.meal} style={{ width: `${(m.calories / totalMeal) * 100}%`, background: MEAL_COLORS[i % MEAL_COLORS.length] }} />
            ))}
          </div>
          <ul className="meal-list">
            {plan.meals.map((m, i) => (
              <li key={m.meal}>
                <span className="legend-dot" style={{ background: MEAL_COLORS[i % MEAL_COLORS.length] }} />
                <span>{m.label}</span>
                <b>about {fmtN(m.calories)} kcal</b>
              </li>
            ))}
          </ul>
        </section>

        {plan.timeline && (
          <section className="sheet">
            <h3>Timeline</h3>
            <p className="plan-big">{plan.timeline.from_kg} → {plan.timeline.to_kg} kg</p>
            <p className="muted">
              About {plan.timeline.weeks} weeks at {plan.timeline.kg_per_week} kg a week, around{" "}
              {new Date(plan.timeline.by_date).toLocaleDateString("en-IN", { month: "long", year: "numeric" })}.
            </p>
          </section>
        )}

        {plan.protein_picks?.length > 0 && (
          <section className="sheet">
            <h3>Protein picks for you</h3>
            <ul className="picks">
              {plan.protein_picks.map((p) => (
                <li key={p.food_id}>
                  <span>{p.native_name || p.name}{p.native_name && <span className="muted small"> {p.name}</span>}</span>
                  <span className="muted small">{p.serving}</span>
                  <b>{p.protein} g</b>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <section className="insights">
        <h2>What this means for you</h2>
        <ul>
          {plan.insights.map((i) => (
            <li key={i.title} className={`insight ${i.kind}`}>
              <h3>{i.title}</h3>
              <p>{i.body}</p>
            </li>
          ))}
        </ul>
        <p className="small muted">A general guide based on your answers, not medical advice. If you have a medical condition, your doctor's targets come first.</p>
      </section>

      {onStart && (
        <div className="plan-cta">
          <button className="btn btn-primary" onClick={onStart} style={{ padding: "0.9rem 1.6rem", fontSize: "1rem" }}>{startLabel}</button>
        </div>
      )}
    </div>
  );
}
