export const FALLBACK_LANGS = [
  { code: "hi", name: "Hindi", native: "हिन्दी" },
  { code: "ta", name: "Tamil", native: "தமிழ்" },
  { code: "te", name: "Telugu", native: "తెలుగు" },
  { code: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
  { code: "ml", name: "Malayalam", native: "മലയാളം" },
  { code: "bn", name: "Bengali", native: "বাংলা" },
  { code: "mr", name: "Marathi", native: "मराठी" },
  { code: "gu", name: "Gujarati", native: "ગુજરાતી" },
  { code: "pa", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
  { code: "or", name: "Odia", native: "ଓଡ଼ିଆ" },
  { code: "as", name: "Assamese", native: "অসমীয়া" },
  { code: "ur", name: "Urdu", native: "اردو" },
  { code: "en", name: "English", native: "English" },
];

export const UNIT_LABELS = {
  piece: "piece", bowl: "katori", cup: "cup", plate: "plate", glass: "glass",
  ladle: "ladle", tbsp: "spoon", tsp: "tsp", handful: "handful", slice: "slice",
  packet: "packet", g: "g", ml: "ml", kg: "kg",
};

export function errorText(err, fallback) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg.replace(/^Value error, /, "");
  if (err?.code === "ERR_NETWORK") return "Can't reach the CALARO server. Check that the backend is running.";
  return fallback;
}

// The API sends naive UTC timestamps; make sure the browser reads them as UTC.
export function toDate(ts) {
  if (!ts) return null;
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts : `${ts}Z`);
}

export const timeOf = (ts) => toDate(ts)?.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
export const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const fmtN = (n) => Math.round(n || 0).toLocaleString("en-IN");

export function greeting(d = new Date()) {
  const h = d.getHours();
  if (h < 5) return "Late night";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function mealLabel(ts) {
  const h = toDate(ts)?.getHours() ?? 12;
  if (h < 11) return "Breakfast";
  if (h < 16) return "Lunch";
  if (h < 19) return "Snack";
  return "Dinner";
}

export function langName(code) {
  return FALLBACK_LANGS.find((l) => l.code === code)?.name || code || "English";
}
