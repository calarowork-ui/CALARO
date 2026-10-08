import { api } from "./client";

export const fetchOverview = () => api.get("/admin/overview").then((r) => r.data);
export const fetchUsers = (q = "") => api.get("/admin/users", { params: { q, limit: 100 } }).then((r) => r.data);
export const setUserActive = (id, is_active) => api.patch(`/admin/users/${id}`, { is_active }).then((r) => r.data);
export const fetchAllLogs = () => api.get("/admin/logs", { params: { limit: 30 } }).then((r) => r.data);

export const fetchAdmins = () => api.get("/admin/admins").then((r) => r.data);
export const createAdmin = (payload) => api.post("/admin/admins", payload).then((r) => r.data);
export const revokeAdmin = (id) => api.delete(`/admin/admins/${id}`).then((r) => r.data);
export const fetchAudit = () => api.get("/admin/audit").then((r) => r.data);

// Monitoring: sets an HttpOnly cookie that lets this browser open /grafana
export const startMonitoring = () => api.post("/admin/monitoring/session", null, { withCredentials: true }).then((r) => r.data);
export const endMonitoring = () => api.post("/admin/monitoring/logout", null, { withCredentials: true }).catch(() => {});
