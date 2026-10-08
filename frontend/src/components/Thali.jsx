import { useEffect, useState } from "react";

/**
 * Today's intake drawn as a steel thali.
 *  - the rim fills with turmeric as calories add up (chilli when over goal)
 *  - four katoris fill for protein, carbs, fat and fibre against their targets
 */
const KATORIS = [
  { key: "protein", label: "Protein", color: "var(--protein)", angle: 198 },
  { key: "carbs", label: "Carbs", color: "var(--carbs)", angle: 246 },
  { key: "fat", label: "Fat", color: "var(--fat)", angle: 294 },
  { key: "fibre", label: "Fibre", color: "var(--fibre)", angle: 342 },
];

export function targetsFor(goal, weightKg) {
  const kcal = goal || 2000;
  return {
    calories: goal || null,
    protein: Math.round(weightKg ? weightKg * 0.8 : 50),
    carbs: Math.round((kcal * 0.5) / 4),
    fat: Math.round((kcal * 0.3) / 9),
    fibre: 30,
  };
}

export function Thali({ totals, targets }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(t);
  }, []);

  const kcal = Math.round(totals?.calories || 0);
  const goal = targets?.calories;
  const pct = goal ? Math.min(kcal / goal, 1) : 0;
  const over = goal && kcal > goal;
  const R = 172;
  const C = 2 * Math.PI * R;

  return (
    <svg className="thali" viewBox="0 0 400 400" role="img"
      aria-label={goal ? `${kcal} of ${goal} calories eaten today` : `${kcal} calories eaten today`}>
      <defs>
        <radialGradient id="steel" cx="42%" cy="38%" r="70%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="60%" stopColor="#eef2f0" />
          <stop offset="100%" stopColor="#cfd8d3" />
        </radialGradient>
        <radialGradient id="well" cx="45%" cy="40%" r="65%">
          <stop offset="0%" stopColor="#fbfcfc" />
          <stop offset="100%" stopColor="#e4eae6" />
        </radialGradient>
        <radialGradient id="bowl" cx="40%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#c9d2cd" />
        </radialGradient>
        {KATORIS.map((k) => (
          <clipPath id={`clip-${k.key}`} key={k.key}>
            <circle r="27" />
          </clipPath>
        ))}
      </defs>

      {/* plate */}
      <circle cx="200" cy="200" r="190" fill="url(#steel)" stroke="#bcc6c0" strokeWidth="1.5" />
      <circle cx="200" cy="200" r="172" fill="none" stroke="#dde3e0" strokeWidth="16" />
      <circle
        className="rim-arc" cx="200" cy="200" r={R} fill="none"
        stroke={over ? "var(--chilli)" : "var(--turmeric)"} strokeWidth="16" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={ready ? C * (1 - pct) : C}
        transform="rotate(-90 200 200)"
      />
      <circle cx="200" cy="200" r="156" fill="url(#well)" stroke="#d3dbd7" strokeWidth="1" />

      {/* katoris along the upper rim */}
      {KATORIS.map((k) => {
        const rad = (k.angle * Math.PI) / 180;
        const x = 200 + 104 * Math.cos(rad);
        const y = 200 + 104 * Math.sin(rad);
        const value = totals?.[k.key] || 0;
        const target = targets?.[k.key] || 1;
        const fill = Math.min(value / target, 1);
        return (
          <g key={k.key} transform={`translate(${x} ${y})`}>
            <title>{`${k.label}: ${Math.round(value)} of ${target} g`}</title>
            <circle r="34" fill="url(#bowl)" stroke="#b8c2bc" strokeWidth="1.2" />
            <circle r="27" fill="#f4f6f5" />
            <g clipPath={`url(#clip-${k.key})`}>
              <rect
                className="katori-fill" x="-27" y="-27" width="54" height="54" fill={k.color} opacity="0.92"
                style={{ transform: `scaleY(${ready ? fill : 0})` }}
              />
            </g>
            <circle r="27" fill="none" stroke="rgba(0,0,0,0.08)" />
            <text y="5" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--ink)" fontFamily="var(--body)"
              style={{ paintOrder: "stroke", stroke: "rgba(255,255,255,0.85)", strokeWidth: 3 }}>{k.label}</text>
          </g>
        );
      })}

      {/* the rice: today's number */}
      <text x="200" y="262" textAnchor="middle" fontFamily="var(--display)" fontWeight="800" fontSize="58"
        fill={over ? "var(--chilli)" : "var(--ink)"} style={{ fontVariantNumeric: "tabular-nums" }}>
        {kcal.toLocaleString("en-IN")}
      </text>
      <text x="200" y="292" textAnchor="middle" fontFamily="var(--body)" fontSize="15" fill="var(--muted)">
        {goal ? `of ${goal.toLocaleString("en-IN")} kcal` : "kcal today"}
      </text>
      {goal ? (
        <text x="200" y="318" textAnchor="middle" fontFamily="var(--body)" fontSize="14" fontWeight="600"
          fill={over ? "var(--chilli)" : "var(--ok)"}>
          {over ? `${(kcal - goal).toLocaleString("en-IN")} over` : `${(goal - kcal).toLocaleString("en-IN")} left`}
        </text>
      ) : null}
    </svg>
  );
}

export function ThaliLegend({ totals, targets }) {
  return (
    <div className="thali-legend">
      {KATORIS.map((k) => (
        <div className="legend-row" key={k.key}>
          <span className="legend-dot" style={{ background: k.color }} />
          <span>{k.label}</span>
          <span style={{ marginLeft: "auto" }}>
            <strong>{Math.round(totals?.[k.key] || 0)}</strong>
            <span className="muted"> / {targets?.[k.key]} g</span>
          </span>
        </div>
      ))}
    </div>
  );
}
