import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Mic, Minus, Plus, Search, SendHorizontal, Square, Trash2, Volume2 } from "lucide-react";

import { createFoodLog } from "../api/food";
import { searchFoods, understandText, understandVoice } from "../api/vaani";
import { blobToWav16kBase64 } from "../lib/wav";
import { FALLBACK_LANGS, UNIT_LABELS, errorText } from "../lib/format";

const EXAMPLES = {
  hi: "दो रोटी, एक कटोरी दाल और थोड़ा चावल",
  ta: "ரெண்டு இட்லி, ஒரு வடை, ஒரு கிண்ணம் சாம்பார்",
  te: "రెండు ఇడ్లీలు, ఒక కప్పు కాఫీ",
  kn: "ಎರಡು ಇಡ್ಲಿ, ಒಂದು ವಡೆ, ಸಾಂಬಾರ್",
  ml: "രണ്ട് പുട്ട്, ഒരു കടല കറി, ഒരു ചായ",
  bn: "দুটো রুটি আর মাছের ঝোল, এক বাটি ভাত",
  mr: "दोन पोळ्या, वरण भात आणि एक वडापाव",
  gu: "બે રોટલી, એક વાટકી દાળ, ભાત અને છાશ",
  pa: "ਦੋ ਰੋਟੀ ਤੇ ਇੱਕ ਕਟੋਰੀ ਦਾਲ",
  or: "ଦୁଇଟି ରୁଟି ଓ ଡାଲି",
  as: "দুখন ৰুটি আৰু এবাটি দাইল",
  ur: "دو روٹی اور ایک کٹوری دال",
  en: "2 idli, a vada and a katori of sambar",
};

const UNIT_ORDER = ["piece", "bowl", "cup", "plate", "glass", "ladle", "tbsp", "tsp", "handful", "slice", "packet", "g", "ml"];
const NUTRIENTS = ["calories", "protein", "carbs", "fat", "fibre"];
const PER_GRAM_KEY = { calories: "kcal", protein: "protein", carbs: "carbs", fat: "fat", fibre: "fibre" };

function recompute(item, quantity, unit) {
  if (!item.per_gram || !item.unit_grams) return { ...item, quantity, unit };
  const grams = Math.max(0, quantity) * (item.unit_grams[unit] ?? item.unit_grams[item.unit] ?? 0);
  const next = { ...item, quantity, unit, grams: Math.round(grams * 10) / 10 };
  NUTRIENTS.forEach((k) => {
    const v = (item.per_gram[PER_GRAM_KEY[k]] || 0) * grams;
    next[k] = k === "calories" ? Math.round(v) : Math.round(v * 10) / 10;
  });
  return next;
}

function stepFor(item) {
  if (item.unit === "g" || item.unit === "ml") return 25;
  if (["bowl", "cup", "plate", "glass"].includes(item.unit)) return 0.5;
  return 1;
}

export function VaaniLogger({ lang, languages, voiceReady, onLanguageChange, onSaved }) {
  const langs = languages?.length ? languages : FALLBACK_LANGS;
  const [phase, setPhase] = useState("idle"); // idle | recording | thinking | review | saving
  const [seconds, setSeconds] = useState(0);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState(null);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => () => {
    clearInterval(timerRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    audioRef.current?.pause();
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    const t = setTimeout(() => {
      searchFoods(query.trim(), lang).then(setSuggestions).catch(() => setSuggestions([]));
    }, 200);
    return () => clearTimeout(t);
  }, [query, lang]);

  const totals = useMemo(() => {
    const t = { calories: 0, protein: 0, carbs: 0, fat: 0, fibre: 0 };
    items.forEach((it) => NUTRIENTS.forEach((k) => (t[k] += Number(it[k]) || 0)));
    return t;
  }, [items]);

  const active = langs.find((l) => l.code === lang) || langs[langs.length - 1];

  const playReply = (b64) => {
    if (!b64) return;
    try {
      audioRef.current?.pause();
      audioRef.current = new Audio(`data:audio/wav;base64,${b64}`);
      audioRef.current.play().catch(() => {});
    } catch {
      /* autoplay may be blocked; the play button stays available */
    }
  };

  const handleResult = (data) => {
    setResult(data);
    setItems(data.items || []);
    setPhase("review");
    if (!data.items?.length) setError("No foods found in that. Try naming the dish, or search below.");
    playReply(data.reply_audio_b64);
  };

  const startRecording = async () => {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser can't record audio. Type your meal instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      recorder.onstop = async () => {
        clearInterval(timerRef.current);
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setPhase("thinking");
        try {
          const audio_b64 = await blobToWav16kBase64(blob);
          handleResult(await understandVoice({ audio_b64, lang }));
        } catch (err) {
          setError(errorText(err, "That recording couldn't be processed. Try again or type it."));
          setPhase(items.length ? "review" : "idle");
        }
      };
      recorder.start();
      setSeconds(0);
      timerRef.current = setInterval(() => {
        setSeconds((s) => {
          if (s >= 45 && recorderRef.current?.state === "recording") recorderRef.current.stop();
          return s + 1;
        });
      }, 1000);
      setPhase("recording");
    } catch {
      setError("Microphone access was blocked. Allow it in the browser's address bar, then try again.");
    }
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };

  const submitText = async (e) => {
    e?.preventDefault();
    if (!typed.trim()) return;
    setError("");
    setPhase("thinking");
    try {
      handleResult(await understandText({ text: typed.trim(), lang, speak: voiceReady }));
    } catch (err) {
      setError(errorText(err, "That couldn't be understood. Try naming each dish."));
      setPhase(items.length ? "review" : "idle");
    }
  };

  const updateItem = (idx, patch) =>
    setItems((prev) => prev.map((it, i) => (i === idx ? recompute(it, patch.quantity ?? it.quantity, patch.unit ?? it.unit) : it)));

  const addFood = (food) => {
    setItems((prev) => [...prev, food]);
    setQuery("");
    setSuggestions([]);
    setError("");
    if (!result) setResult({ native_text: "", english_text: null, warnings: [] });
    setPhase("review");
  };

  const reset = () => {
    setResult(null);
    setItems([]);
    setTyped("");
    setPhase("idle");
    setError("");
  };

  const save = async () => {
    if (!items.length) return;
    setPhase("saving");
    try {
      const native = result?.native_text || typed || "";
      const english = result?.english_text || items.map((i) => `${i.quantity} ${UNIT_LABELS[i.unit] || i.unit} ${i.name}`).join(", ");
      const log = await createFoodLog({ raw_text: english, native_text: native || null, language: lang, items });
      reset();
      onSaved?.(log);
    } catch (err) {
      setError(errorText(err, "The meal wasn't saved. Try again."));
      setPhase("review");
    }
  };

  const busy = phase === "thinking" || phase === "saving";
  const showSlip = phase === "review" || phase === "saving";

  return (
    <section className="leaf" aria-labelledby="speak-title">
      <h2 id="speak-title">What did you eat?</h2>
      <p className="lede">Say it the way you would at home, in your own language. Katori, ladle, tumbler and roti counts all work.</p>

      <div className="lang-row" role="radiogroup" aria-label="Language you'll speak in">
        {langs.map((l) => (
          <button key={l.code} type="button" role="radio" aria-checked={l.code === lang} className="lang-chip"
            onClick={() => onLanguageChange?.(l.code)} title={l.name} lang={l.code}>
            {l.native}
          </button>
        ))}
      </div>

      <div className="speak-row">
        <button type="button" className={`mic ${phase === "recording" ? "live" : ""}`}
          onClick={phase === "recording" ? stopRecording : startRecording}
          disabled={!voiceReady || busy}
          aria-label={phase === "recording" ? "Stop and log" : `Speak in ${active?.name}`}>
          {phase === "thinking" ? <Loader2 className="spin" size={34} /> : phase === "recording" ? <Square size={30} fill="currentColor" /> : <Mic size={36} />}
        </button>
        <div className="speak-hint" aria-live="polite">
          {phase === "recording" && <p className="status">Listening in {active?.native} · {seconds}s. Tap to finish.</p>}
          {phase === "thinking" && <p className="status">Matching your foods…</p>}
          {!["recording", "thinking"].includes(phase) && (
            <>
              <p className="small" style={{ color: "#a3c4b4" }}>{voiceReady ? "Tap and say something like" : "Type something like"}</p>
              <p className="say" lang={lang}>{EXAMPLES[lang] || EXAMPLES.en}</p>
            </>
          )}
        </div>
      </div>

      <form className="type-row" onSubmit={submitText}>
        <input lang={lang} value={typed} onChange={(e) => setTyped(e.target.value)} disabled={phase === "recording" || busy}
          placeholder={`Or type in ${active?.name || "any language"}`} aria-label="Type what you ate" />
        <button type="submit" className="icon-btn" disabled={!typed.trim() || busy} aria-label="Find foods">
          <SendHorizontal size={18} />
        </button>
      </form>

      {!voiceReady && <p className="leaf-warn">Voice is off until Bhashini keys are added to backend/.env. Typing works in every script.</p>}
      {error && <div className="notice error" role="alert">{error}</div>}

      {showSlip && result && (result.native_text || result.reply_text || result.reply_english) && (
            <div className="heard">
              {result.native_text && (
                <>
                  <p className="label">You said</p>
                  <p className="native" lang={lang}>{result.native_text}</p>
                  {result.english_text && result.english_text !== result.native_text && <p className="english">{result.english_text}</p>}
                </>
              )}
              {(result.reply_text || result.reply_english) && items.length > 0 && (
                <div className="reply">
                  <button type="button" className="icon-btn" onClick={() => playReply(result.reply_audio_b64)}
                    disabled={!result.reply_audio_b64} aria-label="Play spoken reply">
                    <Volume2 size={18} />
                  </button>
                  <p lang={result.reply_text ? lang : "en"}>{result.reply_text || result.reply_english}</p>
                </div>
              )}
              {result.warnings?.map((w) => <p key={w} className="leaf-warn">{w}</p>)}
            </div>
      )}

          <div className="slip">
            {items.map((it, idx) => {
              const units = UNIT_ORDER.filter((u) => it.unit_grams?.[u] !== undefined);
              return (
                <div key={`${it.food_id || it.name}-${idx}`} className={`slip-row ${it.matched === false ? "estimated" : ""}`}>
                  <div className="slip-name">
                    <strong lang={it.native_name ? lang : "en"}>{it.native_name || it.name}</strong>
                    <span>{it.native_name ? it.name : `${Math.round(it.grams || 0)} g`}</span>
                    {it.matched === false && <span className="tag">AI estimate</span>}
                  </div>
                  <div className="qty">
                    <button type="button" aria-label={`Less ${it.name}`} onClick={() => updateItem(idx, { quantity: Math.max(0, +(it.quantity - stepFor(it)).toFixed(2)) })}><Minus size={14} /></button>
                    <span className="n">{it.quantity}</span>
                    <button type="button" aria-label={`More ${it.name}`} onClick={() => updateItem(idx, { quantity: +(it.quantity + stepFor(it)).toFixed(2) })}><Plus size={14} /></button>
                    {units.length > 1 ? (
                      <select value={it.unit} onChange={(e) => updateItem(idx, { unit: e.target.value })} aria-label={`Unit for ${it.name}`}>
                        {units.map((u) => <option key={u} value={u}>{UNIT_LABELS[u] || u}</option>)}
                      </select>
                    ) : (
                      <span className="small muted">{UNIT_LABELS[it.unit] || it.unit}</span>
                    )}
                  </div>
                  <div className="kcal">
                    <b>{Math.round(it.calories || 0)}</b>
                    <span>kcal · {Math.round(it.protein || 0)} g protein</span>
                  </div>
                  <button type="button" className="remove" aria-label={`Remove ${it.name}`} onClick={() => setItems((p) => p.filter((_, i) => i !== idx))}>
                    <Trash2 size={16} />
                  </button>
                </div>
              );
            })}

            <div className="add-food">
              <Search size={16} />
              <input lang={lang} value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder={items.length ? "Add a missing dish: dosa, दाल, மீன், ভাত…" : "Or pick dishes by name: dosa, दाल, மீன், ভাত…"} aria-label="Search dishes" />
              {suggestions.length > 0 && (
                <ul className="suggest">
                  {suggestions.map((s) => (
                    <li key={s.food_id}>
                      <button type="button" onClick={() => addFood(s)}>
                        <span lang={s.native_name ? lang : "en"}>{s.native_name || s.name}{s.native_name && <span className="muted small">  {s.name}</span>}</span>
                        <span className="muted small">{s.quantity} {UNIT_LABELS[s.unit] || s.unit} · {s.calories} kcal</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {items.length > 0 && (
              <div className="slip-total">
                <span className="big">{Math.round(totals.calories)} <span className="small muted">kcal</span></span>
                <span className="macro">Protein <b>{totals.protein.toFixed(0)} g</b></span>
                <span className="macro">Carbs <b>{totals.carbs.toFixed(0)} g</b></span>
                <span className="macro">Fat <b>{totals.fat.toFixed(0)} g</b></span>
                <span className="macro">Fibre <b>{totals.fibre.toFixed(0)} g</b></span>
                <div className="slip-actions">
                  <button type="button" className="btn btn-ghost" onClick={reset} disabled={phase === "saving"}>Discard</button>
                  <button type="button" className="btn btn-primary" onClick={save} disabled={phase === "saving"}>
                    {phase === "saving" ? "Saving…" : "Save meal"}
                  </button>
                </div>
              </div>
            )}
          </div>
    </section>
  );
}
