import { api } from "./client";

export async function transcribeVoice(blob) {
  const formData = new FormData();
  formData.append("audio", blob, "voice.webm");

  const { data } = await api.post("/voice/transcribe", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return data;
}

