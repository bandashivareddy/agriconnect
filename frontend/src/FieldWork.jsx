import { useCallback, useEffect, useState } from "react";
import { displayDate, label, useCropApi } from "./cropApi";
import "./CropManagement.css";
import { OfficerActivities } from "./FarmLedger";

const observationTypes = ["general", "crop_condition", "pest", "disease", "weed", "water", "nutrient", "damage"];
const verificationTypes = ["observed_completed", "observed_partial", "not_done", "not_applicable", "unable_to_verify"];
const when = (value) => value ? new Date(value).toLocaleString("en-IN") : "Not recorded";

export function ObservationCard({ observation, onEdit }) {
  return <article className="cm-card"><div className="cm-row"><h3>{observation.title}</h3><span className={observation.severity === "critical" ? "cm-overdue" : "cm-badge"}>{observation.severity}</span></div><p>{label(observation.observation_type)} · {when(observation.observed_at)}</p><p className="cm-instructions">{observation.detailed_notes}</p>{observation.officer_name && <p>Observed by {observation.officer_name}</p>}{onEdit && <button onClick={onEdit}>Edit observation</button>}</article>;
}

function ObservationForm({ initial, busy, onSave, onCancel }) {
  const [form, setForm] = useState(initial || { observation_type: "general", severity: "low", title: "", detailed_notes: "" });
  function field(e) { setForm((old) => ({ ...old, [e.target.name]: e.target.value })); }
  return <form className="cm-form cm-card" onSubmit={(e) => { e.preventDefault(); onSave({ observation_type: form.observation_type, severity: form.severity, title: form.title, detailed_notes: form.detailed_notes, ...(initial ? { observed_at: initial.observed_at, expected_updated_at: initial.updated_at } : {}) }); }}>
    <h3>{initial ? "Edit observation" : "Record field observation"}</h3><p>Record what you see. This is not a diagnosis or a pesticide/fertilizer prescription.</p>
    <label>Observation type<select name="observation_type" value={form.observation_type} onChange={field}>{observationTypes.map((type) => <option key={type} value={type}>{label(type)}</option>)}</select></label>
    <label>Severity<select name="severity" value={form.severity} onChange={field}>{["low", "medium", "high", "critical"].map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
    <label>Short description<input name="title" value={form.title} onChange={field} maxLength="200" required /></label>
    <label>Observed facts<textarea name="detailed_notes" value={form.detailed_notes} onChange={field} required /></label>
    <div className="cm-row"><button type="button" onClick={onCancel}>Cancel</button><button disabled={busy} className="primary-button">Save observation</button></div>
  </form>;
}

function VerifyCard({ task, active, busy, save }) {
  const [status, setStatus] = useState(task.verification_status === "unverified" ? "" : task.verification_status);
  const [note, setNote] = useState(task.officer_note || "");
  return <article className="cm-card"><div className="cm-row"><h3>{task.title}</h3>{task.is_overdue && <span className="cm-overdue">Overdue</span>}</div>
    <p>Due {displayDate(task.due_date)} · Execution: {label(task.status)}</p><p className="cm-instructions">{task.instructions}</p><p><strong>Field verification:</strong> {label(task.verification_status)}</p>
    {task.officer_note && <p className="cm-note">{task.officer_note}</p>}{task.verified_at && <p>Verified {when(task.verified_at)}</p>}
    {active && <form className="cm-form" onSubmit={(e) => { e.preventDefault(); save({ verification_status: status, officer_note: note.trim() || null, expected_updated_at: task.verification_updated_at }); }}>
      <label>What did you verify?<select value={status} onChange={(e) => setStatus(e.target.value)} required><option value="">Select outcome</option>{verificationTypes.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <label>Officer note{status && status !== "observed_completed" ? " (required)" : ""}<textarea value={note} onChange={(e) => setNote(e.target.value)} required={Boolean(status && status !== "observed_completed")} /></label>
      <p>This records field evidence. It does not change the crop task’s execution status.</p><button disabled={busy}>Save verification</button>
    </form>}
  </article>;
}

export function VisitDetail({ api, id, readOnly = false, pathPrefix = "/field-work/visits" }) {
  const [visit, setVisit] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const [editObservation, setEditObservation] = useState(null);
  const [adding, setAdding] = useState(false);
  const [completing, setCompleting] = useState(false);
  const refresh = useCallback(async () => { const data = await api(`${pathPrefix}/${id}`); setVisit(data); setError(""); }, [api, id, pathPrefix]);
  useEffect(() => { let active = true; api(`${pathPrefix}/${id}`).then((data) => { if (active) { setVisit(data); setNotes(data.visit_notes || ""); } }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, id, pathPrefix]);
  async function run(work) { if (busy) return; setBusy(true); setError(""); try { await work(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  const active = !readOnly && visit?.status === "in_progress" && visit?.assignment_status === "active";
  return <section>{error && <p className="cm-error" role="alert">{error}</p>}<button disabled={busy} onClick={() => run(refresh)}>Refresh visit</button>
    {!visit ? <p>{error ? "Visit could not be loaded." : "Loading visit..."}</p> : <>
      <section className="cm-card"><div className="cm-row"><h2>{visit.crop_name}</h2><span className="cm-badge">{label(visit.status)}</span></div>
        <dl className="cm-summary"><div><dt>Farmer / Farm</dt><dd>{visit.farmer_name} / {visit.farm_name}</dd></div><div><dt>Plot</dt><dd>{visit.plot_name || "Not assigned"}</dd></div><div><dt>Planned visit</dt><dd>{displayDate(visit.planned_visit_date)}</dd></div><div><dt>Field Officer</dt><dd>{visit.officer_name}</dd></div><div><dt>Crop Cycle status</dt><dd>{label(visit.cycle.status)}</dd></div><div><dt>Planting / Expected harvest</dt><dd>{displayDate(visit.cycle.planted_on)} / {displayDate(visit.cycle.expected_harvest_on)}</dd></div><div><dt>Started</dt><dd>{when(visit.started_at)}</dd></div><div><dt>Completed</dt><dd>{when(visit.completed_at)}</dd></div></dl>
        {visit.visit_notes && <p className="cm-note">{visit.visit_notes}</p>}
        {!readOnly && visit.status === "planned" && <button className="primary-button" disabled={busy} onClick={() => run(async () => { await api(`/field-work/visits/${id}/status`, "POST", { expected_status: "planned", status: "in_progress", visit_notes: notes || null }); await refresh(); })}>Start visit</button>}
        {active && <><label>Visit notes<textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></label><button disabled={busy} onClick={() => setCompleting(true)}>Complete visit</button></>}
        {completing && active && <div className="cm-note"><p>Complete this visit? Observations and verifications become read-only. Unverified tasks remain recorded as unverified.</p><button disabled={busy} onClick={() => run(async () => { await api(`/field-work/visits/${id}/status`, "POST", { expected_status: "in_progress", status: "completed", visit_notes: notes || null }); setCompleting(false); setAdding(false); setEditObservation(null); await refresh(); })}>Confirm completion</button> <button onClick={() => setCompleting(false)}>Keep working</button></div>}
      </section>
      <h2>Current and overdue Crop Tasks</h2>{!visit.tasks.length && <p>No crop tasks are due for this visit. You can still record observations.</p>}
      {visit.tasks.map((task) => <VerifyCard key={`${task.crop_task_id}-${task.verification_updated_at}-${task.verification_status}`} task={task} active={active} busy={busy} save={(body) => run(async () => { await api(`/field-work/visits/${id}/tasks/${task.crop_task_id}`, "PUT", body); await refresh(); })} />)}
      <h2>Field observations</h2>{active && <button onClick={() => { setAdding(true); setEditObservation(null); }}>+ Add observation</button>}
      {!readOnly && <OfficerActivities api={api} cycle={visit.cycle} visitId={id} canRecord={active} />}
      {active && (adding || editObservation) && <ObservationForm key={editObservation?.observation_id || "new"} initial={editObservation} busy={busy} onCancel={() => { setAdding(false); setEditObservation(null); }} onSave={(body) => run(async () => { await api(`/field-work/visits/${id}/observations${editObservation ? `/${editObservation.observation_id}` : ""}`, editObservation ? "PUT" : "POST", body); setAdding(false); setEditObservation(null); await refresh(); })} />}
      {!visit.observations.length && <p>No observations recorded yet.</p>}{visit.observations.map((obs) => <ObservationCard key={obs.observation_id} observation={obs} onEdit={active ? () => { setEditObservation(obs); setAdding(false); } : undefined} />)}
    </>}
  </section>;
}

function VisitCard({ visit, onOpen }) {
  return <article className="cm-card"><div className="cm-row"><h3>{visit.crop_name}</h3><span className="cm-badge">{label(visit.status)}</span></div><p>{visit.farmer_name} · {visit.farm_name} / {visit.plot_name || "No plot"}</p><p>{displayDate(visit.planned_visit_date)}</p><button onClick={onOpen}>Open visit →</button></article>;
}

export default function FieldWork({ token, onBack }) {
  const api = useCropApi(token);
  const [work, setWork] = useState(null);
  const [id, setId] = useState(null);
  const [selectedCrop, setSelectedCrop] = useState(null);
  const [crop, setCrop] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { let active = true; api("/field-work").then((data) => { if (active) { setWork(data); setError(""); } }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, attempt]);
  useEffect(() => { let active = true; if (!selectedCrop) return; api(`/field-work/crop-cycles/${selectedCrop}`).then((data) => { if (active) setCrop(data); }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, selectedCrop]);
  function back() { if (id || selectedCrop) { setId(null); setSelectedCrop(null); setCrop(null); setAttempt((n) => n + 1); } else onBack(); }
  function visits(title, list) { return <section><h2>{title}</h2>{list.length ? list.map((visit) => <VisitCard key={visit.visit_id} visit={visit} onOpen={() => setId(visit.visit_id)} />) : <p>No visits in this group.</p>}</section>; }
  return <main className="cm-page"><div className="cm-content"><header className="cm-row"><button onClick={back}>← {id || selectedCrop ? "My Field Work" : "Marketplace"}</button><h1>My Field Work</h1></header>
    {error && <p className="cm-error" role="alert">{error}</p>}
    {id ? <VisitDetail key={id} api={api} id={id} /> : selectedCrop ? <section>{crop ? <><h2>{crop.crop_name}</h2><p>{crop.farmer_name} · {crop.farm_name} / {crop.plot_name}</p><p>Crop Cycle: {label(crop.status)}</p><OfficerActivities api={api} cycle={crop} />{visits("Visits for this crop", crop.visits)}</> : <p>Loading assigned crop...</p>}</section> : <>
      <p>Observe field conditions and verify work on your assigned crops. Treatment prescriptions are outside this role.</p><button onClick={() => setAttempt((n) => n + 1)}>Refresh field work</button>
      {!work ? <p>Loading assigned work...</p> : <>
        {visits("Today’s visits", work.visits.filter((v) => v.planned_visit_date === work.business_date))}
        {visits("Upcoming visits", work.visits.filter((v) => v.planned_visit_date > work.business_date && v.status === "planned"))}
        {visits("Earlier unfinished visits", work.visits.filter((v) => v.planned_visit_date < work.business_date && ["planned", "in_progress"].includes(v.status)))}
        <h2>Assigned crops</h2>{!work.assignments.length && <p>No active assignments. An administrator must assign a crop before you can access it.</p>}{work.assignments.map((a) => <article className="cm-card" key={a.assignment_id}><h3>{a.crop_name}</h3><p>{a.farmer_name} · {a.farm_name} / {a.plot_name || "No plot"}</p>{a.notes && <p>{a.notes}</p>}<button onClick={() => { setCrop(null); setSelectedCrop(a.farm_crop_id); }}>Open assigned crop</button></article>)}
        {visits("Completed visits", work.visits.filter((v) => v.status === "completed" && v.planned_visit_date !== work.business_date))}
      </>}
    </>}
  </div></main>;
}

export function FarmerFieldWork({ api, cycleId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [visitId, setVisitId] = useState(null);
  useEffect(() => { let active = true; api(`/my/crop-cycles/${cycleId}/field-work`).then((value) => { if (active) { setData(value); setError(""); } }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, cycleId, attempt]);
  return <section className="cm-card"><div className="cm-row"><h2>Field Officer updates</h2><button onClick={() => setAttempt((n) => n + 1)}>Refresh field updates</button></div>
    {error && <p role="alert">{error}</p>}{!data ? <p>Loading field updates...</p> : <>
      <h3>Assigned officers</h3>{data.assignments.filter((a) => a.status === "active").map((a) => <p key={a.assignment_id}>{a.officer_name} · assigned {when(a.assigned_at)}</p>)}{!data.assignments.some((a) => a.status === "active") && <p>No active field officer assignment.</p>}
      <h3>Latest field visit</h3>{data.visits[0] ? <p>{data.visits[0].officer_name} · {displayDate(data.visits[0].planned_visit_date)} · {label(data.visits[0].status)} <button onClick={() => setVisitId(data.visits[0].visit_id)}>Read visit</button></p> : <p>No visits scheduled yet.</p>}
      <details><summary>Assignment and visit history</summary>{data.assignments.map((a) => <p key={a.assignment_id}>{a.officer_name} · {label(a.status)} · {when(a.assigned_at)}</p>)}{data.visits.map((v) => <p key={v.visit_id}>{displayDate(v.planned_visit_date)} · {v.officer_name} · {label(v.status)} <button onClick={() => setVisitId(v.visit_id)}>Read visit</button></p>)}</details>
      {visitId && <><button onClick={() => setVisitId(null)}>Close visit</button><VisitDetail key={visitId} api={api} id={visitId} readOnly pathPrefix={`/my/crop-cycles/${cycleId}/field-visits`} /></>}
      <h3>Recent observations</h3>{data.observations.length ? data.observations.map((obs) => <ObservationCard key={obs.observation_id} observation={obs} />) : <p>No field observations yet.</p>}
    </>}
  </section>;
}
