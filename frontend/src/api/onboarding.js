import { api } from "./client";

export const completeOnboarding = (answers) => api.post("/onboarding", answers).then((r) => r.data);
export const fetchPlan = () => api.get("/onboarding/plan").then((r) => r.data);
