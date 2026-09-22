import { useCallback } from "react";
import { API_BASE_URL, apiError } from "./api";

export const taskTypes = ["irrigation", "fertilizer", "pest_monitoring", "disease_monitoring", "weed_management", "field_operation", "harvest", "inspection", "general"];
export const scheduleTypes = ["days_after_season_start", "days_before_planting", "days_after_planting", "days_before_harvest", "crop_stage", "condition", "manual"];
export const taskTransitions = {
  pending: ["in_progress", "completed", "partial", "not_applicable", "cancelled"],
  in_progress: ["completed", "partial", "not_applicable", "cancelled"],
  partial: ["in_progress", "completed", "cancelled"],
};
export const label = (value) => value?.replaceAll("_", " ") || "Not recorded";
export const displayDate = (value) => value ? new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "Not recorded";
export function useCropApi(token) {
  return useCallback(async (path, method = "GET", body) => {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok) throw new Error(apiError(data, "Could not save this change. Please retry."));
    return data;
  }, [token]);
}

export const taskPhases = ["pre_season", "planting", "crop_stage", "harvest", "miscellaneous"];
export const phaseLabel = (phase, lifecycle) => phase === "pre_season" ? (lifecycle === "perennial" ? "Pre-season" : "Pre-plantation") : label(phase);
export const seasonLabel = (start, lifecycle) => !start ? "" : lifecycle === "perennial" ? `${start.slice(0, 4)}-${String(Number(start.slice(0, 4)) + 1).slice(-2)}` : start.slice(0, 4);
