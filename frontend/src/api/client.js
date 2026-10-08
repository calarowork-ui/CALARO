import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export const api = axios.create({ baseURL: API_BASE_URL, timeout: 30000 });

function readToken() {
  try {
    return localStorage.getItem("calaro_token");
  } catch {
    return null;
  }
}

api.interceptors.request.use((config) => {
  const token = readToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Expired or revoked session: drop the token and send the person back to sign in.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && readToken()) {
      try {
        localStorage.removeItem("calaro_token");
      } catch {
        /* ignore */
      }
      window.dispatchEvent(new Event("calaro:signed-out"));
    }
    return Promise.reject(err);
  }
);
