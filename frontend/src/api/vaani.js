import { api } from "./client";

export async function fetchVaaniStatus() {
  const { data } = await api.get("/vaani/status");
  return data;
}

export async function understandVoice({ audio_b64, lang, speak = true }) {
  const { data } = await api.post("/vaani/voice", { audio_b64, lang, speak }, { timeout: 90000 });
  return data;
}

export async function understandText({ text, lang, speak = true }) {
  const { data } = await api.post("/vaani/text", { text, lang, speak }, { timeout: 60000 });
  return data;
}

export async function searchFoods(q, lang) {
  const { data } = await api.get("/vaani/foods", { params: { q, lang, limit: 8 } });
  return data;
}

export async function fetchToday() {
  const { data } = await api.get("/vaani/today");
  return data;
}
