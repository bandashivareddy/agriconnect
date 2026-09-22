// Display wording only. API payloads and decisions continue to use stable codes.
export const cropStatusLabel = (cycle) => ({
  planned: "Planned", active: "Growing",
  harvested: cycle.perennial_planting_id ? "Season Closed" : "Completed",
  cancelled: "Cancelled",
}[cycle.status] || "Not recorded");

export const taskActionLabel = (status) => ({
  in_progress: "Start task", completed: "Complete task", partial: "Partly completed",
  not_applicable: "Not applicable", cancelled: "Cancel task", pending: "Return to pending",
}[status] || status.replaceAll("_", " "));

export const planName = (name) => name?.replaceAll("_", " ").replace(/\bsop\b/gi, "plan") || "Crop Plan";
