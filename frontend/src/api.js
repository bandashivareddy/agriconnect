export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export function apiError(data, fallback) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg).join(". ");
  return fallback;
}
