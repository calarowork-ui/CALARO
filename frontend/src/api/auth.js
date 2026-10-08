import { api } from "./client";

export async function registerUser(payload) {
  const { data } = await api.post("/auth/register", payload);
  return data;
}

export async function loginUser({ email, password }) {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);

  const { data } = await api.post("/auth/login", body, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  return data;
}

export async function fetchMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

export async function fetchProfile() {
  const { data } = await api.get("/auth/profile");
  return data;
}

export async function updateProfile(payload) {
  const { data } = await api.put("/auth/profile", payload);
  return data;
}

export async function requestPasswordReset(email) {
  const { data } = await api.post("/password-reset/request-otp", { email });
  return data;
}

export async function resetPassword(email, otp, new_password) {
  const { data } = await api.post("/password-reset/reset-password", { email, otp, new_password });
  return data;
}
