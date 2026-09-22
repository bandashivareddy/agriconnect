import { useEffect, useState } from "react";
import { label, taskPhases, scheduleTypes, taskTypes, useCropApi } from "./cropApi";
import "./CropManagement.css";

const emptyTask = { phase: "miscellaneous", sequence_no: 1, title: "", instructions: "", task_type: "general", schedule_type: "days_after_planting", offset_days: 0, crop_stage_key: "", condition_text: "" };

function DraftTaskForm({ api, task, nextSequence, busy, onSave, onCancel }) {
  const [form, setForm] = useState(task ? { ...task, crop_stage_key: task.crop_stage_key || "", condition_text: task.condition_text || "", offset_days: task.offset_days ?? 0 } : { ...emptyTask, sequence_no: nextSequence });
  const [categories, setCategories] = useState([]);
  const [categoryError, setCategoryError] = useState("");
  const [categoryAttempt, setCategoryAttempt] = useState(0);
  useEffect(() => { let active = true; api("/service-categories").then((data) => { if (active) { setCategories(data); setCategoryError(""); } }).catch((err) => { if (active) setCategoryError(err.message); }); return () => { active = false; }; }, [api, categoryAttempt]);
  const relative = ["days_after_season_start", "days_before_planting", "days_after_planting", "days_before_harvest"].includes(form.schedule_type);
  function field(event) { setForm((old) => ({ ...old, [event.target.name]: event.target.value })); }
  return <section className="cm-card"><h3>{task ? "Edit draft task" : "Add draft task"}</h3><form className="cm-form" onSubmit={(event) => { event.preventDefault(); onSave({
    sequence_no: Number(form.sequence_no), title: form.title, instructions: form.instructions, task_type: form.task_type,
    phase: form.phase || null, schedule_type: form.schedule_type, offset_days: relative ? Number(form.offset_days) : null,
    crop_stage_key: form.schedule_type === "crop_stage" ? form.crop_stage_key : null,
    service_category_id: form.service_category_id ? Number(form.service_category_id) : null,
    condition_text: form.schedule_type === "condition" ? form.condition_text : null,
  }); }}>
    <label>Sequence<input type="number" name="sequence_no" value={form.sequence_no} onChange={field} min="1" required /></label>
    <label>Task title<input name="title" value={form.title} onChange={field} maxLength="200" required /></label>
    <label>Instructions<textarea name="instructions" value={form.instructions} onChange={field} required /></label>
    <label>Task type<select name="task_type" value={form.task_type} onChange={field}>{taskTypes.map((type) => <option key={type} value={type}>{label(type)}</option>)}</select></label>
    <label>Bookable service category (optional)<select name="service_category_id" value={form.service_category_id || ""} onChange={field}><option value="">No service requirement</option>{form.service_category_id && !categories.some((c) => c.category_id === Number(form.service_category_id)) && <option value={form.service_category_id}>{form.service_category_name_snapshot || "Saved category"}</option>}{categories.map((c) => <option key={c.category_id} value={c.category_id}>{c.category_name}</option>)}</select></label>
    {categoryError && <p role="alert">{categoryError} <button type="button" onClick={() => setCategoryAttempt((n) => n + 1)}>Reload categories</button></p>}
    <label>Task phase<select name="phase" value={form.phase || ""} onChange={field} required><option value="">Select phase</option>{taskPhases.map((phase) => <option key={phase} value={phase}>{phase === "pre_season" ? "Pre-season / Pre-plantation" : label(phase)}</option>)}</select></label>
    <label>Scheduling<select name="schedule_type" value={form.schedule_type} onChange={field}>{scheduleTypes.map((type) => <option key={type} value={type}>{label(type)}</option>)}</select></label>
    {relative && <label>{label(form.schedule_type)}<input type="number" name="offset_days" value={form.offset_days} onChange={field} min="0" max="36500" required /></label>}
    {form.schedule_type === "crop_stage" && <label>Crop stage label (for this SOP)<input name="crop_stage_key" value={form.crop_stage_key} onChange={field} maxLength="100" required /></label>}
    {form.schedule_type === "condition" && <label>Condition description<textarea name="condition_text" value={form.condition_text} onChange={field} required /></label>}
    {!relative && <p className="cm-note">No automatic due date. The farmer decides when this stage, condition or manual task applies.</p>}
    <div className="cm-row"><button type="button" onClick={onCancel}>Cancel edit</button><button className="primary-button" disabled={busy}>Save draft task</button></div>
  </form></section>;
}

function VersionEditor({ api, version, busy, run, reload, onChanged }) {
  const [notes, setNotes] = useState(version.version_notes || "");
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [retiring, setRetiring] = useState(false);
  const draft = version.status === "draft";
  async function action(path, method = "POST", body) { await api(path, method, body); await reload(); await onChanged(); }
  return <section><div className="cm-card"><div className="cm-row"><h2>Version {version.version_number}</h2><span className="cm-badge">{version.status}</span><button disabled={busy} onClick={() => run(reload)}>Refresh version</button></div>
    {draft ? <form className="cm-form" onSubmit={(event) => { event.preventDefault(); run(() => action(`/admin/sop-versions/${version.sop_version_id}`, "PATCH", { version_notes: notes || null })); }}><label>Version notes<textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></label><button disabled={busy}>Save version notes</button></form> : <p>{version.version_notes || "No version notes."}</p>}
    {!draft && <p>Published content is immutable. Create a new draft from this version to make changes.</p>}
    <div className="cm-row">
      {draft && <button disabled={busy || !version.tasks.length} className="primary-button" onClick={() => run(() => action(`/admin/sop-versions/${version.sop_version_id}/publish`))}>Publish version</button>}
      {version.status === "published" && <button disabled={busy} onClick={() => setRetiring(true)}>Retire version</button>}
    </div>
    {retiring && <div className="cm-note"><p>Retirement prevents new plans. Existing crop plans continue unchanged.</p><button disabled={busy} onClick={() => run(async () => { await action(`/admin/sop-versions/${version.sop_version_id}/retire`); setRetiring(false); })}>Confirm retirement</button> <button onClick={() => setRetiring(false)}>Keep published</button></div>}
  </div>
  <h2>Version tasks</h2>{!version.tasks.length && <p>Add at least one task before publishing.</p>}
  {version.tasks.map((task) => <article className="cm-card" key={task.sop_task_id}><h3>{task.sequence_no}. {task.title}</h3><p>{label(task.phase)} / {label(task.task_type)} · {label(task.schedule_type)}{task.offset_days != null ? ` · ${task.offset_days} days` : ""}</p><p className="cm-instructions">{task.instructions}</p>{task.crop_stage_key && <p>Stage: {task.crop_stage_key}</p>}{task.condition_text && <p>Condition: {task.condition_text}</p>}{task.service_category_name_snapshot && <p>Service category: {task.service_category_name_snapshot}</p>}
    {draft && <div className="cm-row"><button disabled={busy} onClick={() => { setEditing(task); setAdding(false); }}>Edit task</button><button disabled={busy} onClick={() => setDeleting(task.sop_task_id)}>Delete draft task</button></div>}
    {deleting === task.sop_task_id && <p>Delete this draft task? <button disabled={busy} onClick={() => run(async () => { await action(`/admin/sop-tasks/${task.sop_task_id}`, "DELETE"); setDeleting(null); if (editing?.sop_task_id === task.sop_task_id) setEditing(null); })}>Confirm delete</button> <button onClick={() => setDeleting(null)}>Keep task</button></p>}
  </article>)}
  {draft && <button disabled={busy} onClick={() => { setAdding(true); setEditing(null); }}>+ Add task</button>}
  {draft && (adding || editing) && <DraftTaskForm api={api} key={editing?.sop_task_id || "new"} task={editing} nextSequence={Math.max(0, ...version.tasks.map((t) => t.sequence_no)) + 1} busy={busy} onCancel={() => { setAdding(false); setEditing(null); }} onSave={(body) => run(async () => {
    await action(editing ? `/admin/sop-tasks/${editing.sop_task_id}` : `/admin/sop-versions/${version.sop_version_id}/tasks`, editing ? "PATCH" : "POST", body);
    setAdding(false); setEditing(null);
  })} />}
  </section>;
}

export default function SopManagement({ token, onBack }) {
  const api = useCropApi(token);
  const [templates, setTemplates] = useState([]);
  const [crops, setCrops] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [versions, setVersions] = useState([]);
  const [version, setVersion] = useState(null);
  const [form, setForm] = useState({ crop_id: "", name: "", description: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try { const [ts, cs] = await Promise.all([api("/admin/sop-templates"), api("/crops")]); if (active) { setTemplates(ts); setCrops(cs); setError(""); } }
      catch (err) { if (active) setError(err.message); }
      finally { if (active) setLoading(false); }
    }
    load(); return () => { active = false; };
  }, [api, attempt]);
  async function run(work) { if (busy) return; setBusy(true); setError(""); try { await work(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  async function loadVersions() { setVersions(await api(`/admin/sop-templates/${templateId}/versions`)); }
  async function createVersion(clone) {
    const data = await api(`/admin/sop-templates/${templateId}/versions`, "POST", clone ? { clone_from_version_id: clone } : {});
    await loadVersions(); setVersion(await api(`/admin/sop-versions/${data.sop_version_id}`));
  }
  return <main className="cm-page"><div className="cm-content"><header className="cm-row"><button onClick={onBack}>← Admin dashboard</button><h1>Crop SOPs</h1></header>
    <p>Create reusable crop instructions, publish immutable versions, and let farmers generate their crop plans.</p>
    {error && <div className="cm-error" role="alert">{error} <button onClick={() => setAttempt((n) => n + 1)}>Reload templates</button></div>}
    {loading ? <p>Loading SOPs...</p> : <>
    <section className="cm-card"><h2>Create SOP template</h2><form className="cm-form" onSubmit={(event) => { event.preventDefault(); run(async () => {
      const created = await api("/admin/sop-templates", "POST", { ...form, crop_id: Number(form.crop_id), description: form.description || null });
      setTemplates(await api("/admin/sop-templates")); setTemplateId(String(created.sop_template_id)); setVersions([]); setVersion(null); setForm({ crop_id: "", name: "", description: "" });
    }); }}>
      <label>Crop<select value={form.crop_id} onChange={(e) => setForm({ ...form, crop_id: e.target.value })} required><option value="">Choose crop</option>{crops.map((crop) => <option key={crop.crop_id} value={crop.crop_id}>{crop.crop_name}</option>)}</select></label>
      <label>Template name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} minLength="2" maxLength="150" required /></label>
      <label>Description<textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
      <button disabled={busy || !crops.length}>Create template</button>
    </form></section>
    <section className="cm-card"><h2>Manage versions</h2><div className="cm-form">
      <label>SOP template<select value={templateId} disabled={busy} onChange={(event) => { const id = event.target.value; setTemplateId(id); setVersion(null); setVersions([]); if (id) run(async () => setVersions(await api(`/admin/sop-templates/${id}/versions`))); }}><option value="">Choose template</option>{templates.map((t) => <option key={t.sop_template_id} value={t.sop_template_id}>{t.name} · {t.crop_name}{t.is_active ? "" : " (inactive)"}</option>)}</select></label>
      {templateId && <><label>Version<select value={version?.sop_version_id || ""} disabled={busy} onChange={(event) => { const id = event.target.value; setVersion(null); if (id) run(async () => setVersion(await api(`/admin/sop-versions/${id}`))); }}><option value="">Choose version</option>{versions.map((v) => <option key={v.sop_version_id} value={v.sop_version_id}>Version {v.version_number} · {v.status}</option>)}</select></label><div className="cm-row"><button disabled={busy} onClick={() => run(() => createVersion())}>+ New empty draft</button>{version && <button disabled={busy} onClick={() => run(() => createVersion(version.sop_version_id))}>New draft from this version</button>}</div></>}
    </div></section>
    {version && <VersionEditor key={`${version.sop_version_id}-${version.status}`} api={api} version={version} busy={busy} run={run} reload={async () => setVersion(await api(`/admin/sop-versions/${version.sop_version_id}`))} onChanged={loadVersions} />}
    </>}
  </div></main>;
}
