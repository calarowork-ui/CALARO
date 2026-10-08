import { api } from "./client";

export async function parseFood(text) {
  const { data } = await api.post("/food/parse", null, {
    params: { text },
  });
  return data;
}

export async function createFoodLog(payload) {
  const { data } = await api.post("/food/logs", payload);
  return data;
}

export async function fetchFoodLogs() {
  const { data } = await api.get("/food/logs");
  return data;
}


export async function deleteFoodLog(id) {
  await api.delete(`/food/logs/${id}`);
}
