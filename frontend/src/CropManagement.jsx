import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { revealInvalidField } from "./farmerUx";
import { useCallback, useEffect, useState } from "react";
import { displayDate, label, phaseLabel, seasonLabel, taskTransitions, useCropApi } from "./cropApi";
import "./CropManagement.css";
import { cropStatusLabel, taskActionLabel, planName } from "./farmerLabels";
import MyBookings from "./MyBookings";
import { TaskServiceActions, TaskServiceBooking } from "./TaskServices";
import { FarmerFieldWork } from "./FieldWork";
import FarmLedger, { ActivityForm, ExpenseForm } from "./FarmLedger";
import CropHarvests, { HarvestSummary } from "./CropHarvests";
import { CompletionReview, SeasonPanel, PerennialPlantings } from "./ProductionLifecycle";
import { PlantingFields, PlantingSummary, PlantingEdit } from "./CropInputs";

function CycleSummary({ cycle }) {
  useTranslation();
  const plan = cycle.plan;
  return <dl className="cm-summary">
    <div><dt>{t("Farm / Plot")}</dt><dd>{cycle.farm_name} / {cycle.plot_name || t("No plot assigned")}</dd></div>
    {cycle.farm_block_id && <div><dt>{t("Block")}</dt><dd>{cycle.block_name || t("Block #{{v0}}", { v0: cycle.farm_block_id })}</dd></div>}
    {cycle.season && <div><dt>{t("Season")}</dt><dd>{cycle.season}</dd></div>}
    {cycle.period_started_on && <div><dt>{t("Season start")}</dt><dd>{displayDate(cycle.period_started_on)}</dd></div>}
    <div><dt>{t("Status")}</dt><dd>{cropStatusLabel(cycle)}</dd></div>
    {cycle.crop_group && <div><dt>{t("Crop group")}</dt><dd>{label(cycle.crop_group)}{cycle.lifecycle_type ? ` · ${label(cycle.lifecycle_type)}` : ""}</dd></div>}
    <div><dt>{cycle.status === "planned" ? t("Expected planting date") : t("Actual planting date")}</dt><dd>{displayDate(cycle.status === "planned" ? cycle.expected_planting_on || plan?.anchor_date : cycle.planted_on)}</dd></div>
    <div><dt>{t("Expected harvest")}</dt><dd>{displayDate(cycle.expected_harvest_on)}</dd></div>
    <div><dt>{t("Crop plan")}</dt><dd>{plan ? planName(plan.sop_template_name_snapshot) : t("No plan yet")}</dd></div>
    <div><dt>{t("Progress")}</dt><dd>{cycle.summary.completed_tasks} / {cycle.summary.total_tasks}{t(" tasks completed · ")}{cycle.summary.overdue_tasks}{t(" overdue")}</dd></div>
    <div><dt>{t("Next task")}</dt><dd>{cycle.summary.next_task ? `${cycle.summary.next_task.title} · ${displayDate(cycle.summary.next_task.due_date)}` : t("No unfinished tasks")}</dd></div>
  </dl>;
}

export function CropListCard({ cycle, history, onOpen }) {
  useTranslation();
  const variety = cycle.planting_snapshot?.variety;
  const planted = cycle.planted_on || cycle.expected_planting_on || cycle.plan?.anchor_date;
  return <article className="cm-card cm-open-card"><div className="cm-row"><h2>{cycle.crop_name}</h2><span className="cm-badge">{cropStatusLabel(cycle)}</span></div>
    <p>{[cycle.farm_name, cycle.plot_name, cycle.block_name || (cycle.farm_block_id ? `Block #${cycle.farm_block_id}` : null)].filter(Boolean).join(" · ")}</p>
    {cycle.season && <p>{t("Season: ")}{cycle.season}</p>}
    {!history && variety?.variety_name && <p>{t("Variety: ")}{variety.variety_name}</p>}
    {planted && <p>{cycle.planted_on ? t("Planted") : t("Expected planting")}: {displayDate(planted)}</p>}
    {!history && (variety?.duration_min_days || variety?.duration_max_days) && <p>{t("Approximate duration: ")}{variety.duration_min_days || "?"}–{variety.duration_max_days || "?"}{t(" days")}</p>}
    {cycle.expected_harvest_on && <p>{t("Expected harvest: ")}{displayDate(cycle.expected_harvest_on)}</p>}
    {!history && cycle.summary?.next_task && <p>{t("Next task: ")}{cycle.summary.next_task.title} · {displayDate(cycle.summary.next_task.due_date)}</p>}
    {!history && cycle.summary?.overdue_tasks > 0 && <p className="cm-overdue">{cycle.summary.overdue_tasks}{t(" overdue tasks")}</p>}
    <button className="cm-open-card-button" aria-label={t("Open {{v0}}, {{v1}}, {{v2}}", { v0: cycle.crop_name, v1: cycle.farm_name, v2: cycle.season || cropStatusLabel(cycle) })} onClick={onOpen}>{history ? t("View History") : t("Open Crop")}</button>
  </article>;
}

function OverviewRecords({ api, id, onTab }) {
  useTranslation();
  const [expenses, setExpenses] = useState(null);
  const [activities, setActivities] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.allSettled([api(`/my/crop-cycles/${id}/harvest-summary`), api(`/my/farm-activities?farm_crop_id=${id}&limit=3`)]).then(([costs, work]) => {
      if (!active) return;
      if (costs.status === "fulfilled") setExpenses(costs.value);
      if (work.status === "fulfilled") setActivities(work.value);
      setError(costs.status === "rejected" || work.status === "rejected" ? "Some recent records could not be loaded." : "");
    });
    return () => { active = false; };
  }, [api, id, attempt]);
  return <section className="cm-card"><h2>{t("Work & crop finances")}</h2>{error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}
    {expenses && <HarvestSummary summary={expenses} financialOnly />}
    {activities && activities.items.length ? <ul>{activities.items.map((a) => <li key={a.activity_id}>{displayDate(a.activity_date)} · {a.description}</li>)}</ul> : <p>{t("No activities recorded yet.")}</p>}
    {!expenses && !activities && !error && <p>{t("Loading recent records…")}</p>}
    <div className="cm-row"><button onClick={() => onTab("activities")}>{t("View Activities")}</button><button onClick={() => onTab("expenses")}>{t("View Expenses")}</button><button onClick={() => onTab("harvests")}>{t("View Harvests")}</button></div>
  </section>;
}

function NewCycle({ api, farms, crops, onCreated, onFarms, run, busy, initialContext }) {
  useTranslation();
  const [plantingDetails, setPlantingDetails] = useState({});
  const [tracking, setTracking] = useState("self");
  const [form, setForm] = useState({ farm_id: String(initialContext?.farm_id || (farms.length === 1 ? farms[0].farm_id : "")), plot_id: String(initialContext?.plot_id || ""), crop_id: "", season: "", period_started_on: "", expected_planting_on: "", status: "planned", planted_on: "", expected_harvest_on: "" });
  const [plots, setPlots] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const [blockId, setBlockId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (!form.farm_id) return;
    async function load() {
      setLoading(true); setError("");
      try { const [data, savedBlocks] = await Promise.all([api(`/my/farms/${form.farm_id}`), api(`/my/farm-blocks?farm_id=${form.farm_id}`)]); if (active) { setPlots(data.plots); setBlocks(savedBlocks); if (data.plots.length === 1) setForm((old) => ({ ...old, plot_id: String(data.plots[0].plot_id) })); } }
      catch (err) { if (active) setError(err.message); }
      finally { if (active) setLoading(false); }
    }
    load(); return () => { active = false; };
  }, [api, form.farm_id]);
  function field(event) { const { name, value } = event.target; if (name === "crop_id") setPlantingDetails({}); if (["farm_id", "plot_id"].includes(name)) setBlockId(""); setForm((old) => ({ ...old, [name]: value, ...(name === "farm_id" ? { plot_id: "" } : {}) })); }
  function submit(event) {
    event.preventDefault();
    run(async () => {
      const cycle = await api(`/my/farms/${form.farm_id}/crop-cycles`, "POST", {
        plot_id: Number(form.plot_id), farm_block_id: blockId ? Number(blockId) : null, crop_id: Number(form.crop_id), season: form.season || null, period_started_on: form.period_started_on, expected_planting_on: form.expected_planting_on || null,
        status: form.status, planted_on: form.status === "active" ? form.planted_on : null, expected_harvest_on: form.expected_harvest_on || null,
        crop_variety_id: plantingDetails.crop_variety_id || null, planting_material_source_id: plantingDetails.planting_material_source_id || null, seed_or_material_lot: plantingDetails.seed_or_material_lot || null, variety_text: plantingDetails.variety_text || null,
      });
      await onCreated(cycle, tracking);
    });
  }
  return <section className="cm-card"><h2>{t("Start Crop")}</h2><p>{t("Choose where you will grow this crop. A crop plan is optional.")}</p>
    <form onInvalid={revealInvalidField} className="cm-form" onSubmit={submit}>
      <label>{t("Farm")}<select name="farm_id" value={form.farm_id} onChange={field} required><option value="">{t("Select farm")}</option>{farms.map((farm) => <option key={farm.farm_id} value={farm.farm_id}>{farm.farm_name}</option>)}</select></label>
      <label>{t("Plot")}<select name="plot_id" value={form.plot_id} onChange={field} required disabled={loading || !form.farm_id}><option value="">{loading ? t("Loading plots...") : t("Select plot")}</option>{plots.map((plot) => <option key={plot.plot_id} value={plot.plot_id}>{plot.plot_name}</option>)}</select></label>
      <label>{t("Block (optional)")}<select value={blockId} onChange={(e) => setBlockId(e.target.value)} disabled={!form.plot_id || loading}><option value="">{t("Whole plot / no block")}</option>{blocks.filter((b) => b.plot_id === Number(form.plot_id) && b.status === "active").map((b) => <option key={b.farm_block_id} value={b.farm_block_id}>{b.name}</option>)}</select></label>
      {!farms.length || form.farm_id && !loading && !plots.length && <p>{t("Add a farm and plot first. ")}<button type="button" onClick={onFarms}>{t("Open My Farms")}</button></p>}
      {error && <p role="alert">{messageText(error)}</p>}
      <label>{t("Crop")}<select name="crop_id" value={form.crop_id} onChange={field} required><option value="">{t("Select crop")}</option>{crops.map((crop) => <option key={crop.crop_id} value={crop.crop_id}>{crop.crop_name}</option>)}</select></label>
      {!crops.length && <p>{t("The crop catalogue is empty. Contact your administrator before creating a cycle.")}</p>}
      <label>{t("Season start")}<input type="date" name="period_started_on" value={form.period_started_on} onChange={field} required /></label>
      <p>{t("Season: ")}{form.season || seasonLabel(form.period_started_on, crops.find((c) => c.crop_id === Number(form.crop_id))?.lifecycle_type) || t("Choose season start")}</p>
      <details><summary>{t("Correct season label (optional)")}</summary><label>{t("Custom label")}<input name="season" value={form.season} onChange={field} maxLength={50} /></label></details>
      {form.status === "planned" && <label>{t("Expected planting date (optional)")}<input type="date" name="expected_planting_on" value={form.expected_planting_on} onChange={field} /></label>}
      <label>{t("Has planting happened?")}<select name="status" value={form.status} onChange={field}><option value="planned">{t("Not yet")}</option><option value="active">{t("Yes, already planted")}</option></select></label>
      {form.status === "active" && <label>{t("Actual planting date")}<input type="date" name="planted_on" value={form.planted_on} onChange={field} required /></label>}
      <PlantingFields key={form.crop_id} api={api} cropId={form.crop_id} value={plantingDetails} onChange={setPlantingDetails} plantingDate={crops.find((c) => c.crop_id === Number(form.crop_id))?.lifecycle_type === "perennial" ? null : form.status === "active" ? form.planted_on : form.expected_planting_on || null} onHarvestSuggestion={(value) => setForm({ ...form, expected_harvest_on: value })} />
      <label>{t("Expected harvest date")}<input type="date" name="expected_harvest_on" value={form.expected_harvest_on} onChange={field} min={form.status === "active" ? form.planted_on : undefined} /></label>
      <fieldset><legend>{t("How would you like to track this crop?")}</legend><div className="cm-row">{[["self", "Track Myself"], ["plan", "Use Crop Plan"]].map(([code, title]) => <button key={code} type="button" aria-pressed={tracking === code} onClick={() => setTracking(code)}>{title}</button>)}</div></fieldset>
      <button className="primary-button" disabled={busy || loading}>{t("Create and open crop")}</button>
    </form></section>;
}

function SeasonDates({ api, cycle, refresh, run, busy }) {
  useTranslation();
  const [start, setStart] = useState(cycle.period_started_on || "");
  const [expected, setExpected] = useState(cycle.expected_planting_on || "");
  const [harvest, setHarvest] = useState(cycle.expected_harvest_on || "");
  if (!["planned", "active"].includes(cycle.status)) return null;
  return <details className="cm-card"><summary>{cycle.period_started_on ? t("Season dates") : t("Set season start")}</summary><form onInvalid={revealInvalidField} className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api(`/my/crop-cycles/${cycle.farm_crop_id}`, "PATCH", { ...(!cycle.perennial_planting_id ? { period_started_on: start } : {}), expected_planting_on: expected || null, expected_harvest_on: harvest || null }); await refresh(); }); }}>
    <label>{t("Season start")}<input type="date" required value={start} readOnly={!!cycle.perennial_planting_id} onChange={(e) => setStart(e.target.value)} /></label>
    {cycle.status === "planned" && <label>{t("Expected planting")}<input type="date" value={expected} onChange={(e) => setExpected(e.target.value)} /></label>}
    <label>{t("Expected harvest")}<input type="date" value={harvest} onChange={(e) => setHarvest(e.target.value)} /></label>
    <p>{t("Existing plan dates remain unchanged when these dates are corrected.")}</p><button disabled={busy}>{t("Save dates")}</button>
  </form></details>;
}

function AssignExistingPlot({ api, cycle, run, busy, refresh, onFarms }) {
  useTranslation();
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api(`/my/farms/${cycle.farm_id}`).then((data) => { if (active) setPlots(data.plots); }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, cycle.farm_id]);
  return <section className="cm-card"><h2>{t("Assign a plot")}</h2><p>{t("This existing cultivation record needs a plot before a plan can be generated.")}</p>
    {error && <p role="alert">{messageText(error)}</p>}
    {plots.length ? <form onInvalid={revealInvalidField} className="cm-form" onSubmit={(event) => { event.preventDefault(); run(async () => { await api(`/my/crop-cycles/${cycle.farm_crop_id}`, "PATCH", { plot_id: Number(plotId) }); await refresh(); }); }}>
      <label>{t("Plot")}<select value={plotId} onChange={(e) => setPlotId(e.target.value)} required><option value="">{t("Select plot")}</option>{plots.map((plot) => <option key={plot.plot_id} value={plot.plot_id}>{plot.plot_name}</option>)}</select></label><button disabled={busy}>{t("Assign plot")}</button>
    </form> : <button onClick={onFarms}>{t("Add a plot in My Farms")}</button>}
  </section>;
}

function PlanSetup({ api, cycle, run, busy, refresh, onFarms }) {
  useTranslation();
  const [templates, setTemplates] = useState([]);
  const [versions, setVersions] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [preview, setPreview] = useState(null);
  const [anchor, setAnchor] = useState(cycle.planted_on || cycle.expected_planting_on || "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true); setError("");
      try { const data = await api(`/sop-templates?crop_id=${cycle.crop_id}`); if (active) setTemplates(data); }
      catch (err) { if (active) setError(err.message); }
      finally { if (active) setLoading(false); }
    }
    load(); return () => { active = false; };
  }, [api, cycle.crop_id, attempt]);
  function selectTemplate(event) {
    const id = event.target.value; setTemplateId(id); setVersionId(""); setPreview(null); setVersions([]);
    if (id) run(async () => { const items = await api(`/sop-templates/${id}/versions`); setVersions(items); if (items.length === 1) { setVersionId(String(items[0].sop_version_id)); setPreview(await api(`/sop-versions/${items[0].sop_version_id}`)); } });
  }
  function selectVersion(event) {
    const id = event.target.value; setVersionId(id); setPreview(null);
    if (id) run(async () => setPreview(await api(`/sop-versions/${id}`)));
  }
  if (!cycle.plot_id) return <AssignExistingPlot api={api} cycle={cycle} run={run} busy={busy} refresh={refresh} onFarms={onFarms} />;
  return <section className="cm-card"><h2>{t("Select a Crop Plan")}</h2>
    {loading && <p>{t("Loading crop plans...")}</p>}
    {error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}
    {!loading && !error && !templates.length && <p>{t("No crop plan is available for ")}{cycle.crop_name}{t(". You can record work and expenses while your administrator prepares a plan. Your crop is saved.")}</p>}
    <form onInvalid={revealInvalidField} className="cm-form" onSubmit={(event) => { event.preventDefault(); run(async () => { await api(`/my/crop-cycles/${cycle.farm_crop_id}/plan`, "POST", { sop_version_id: Number(versionId), anchor_date: anchor || null }); await refresh(); }); }}>
      <label>{t("Crop plan")}<select value={templateId} onChange={selectTemplate} required disabled={busy}><option value="">{t("Choose a plan")}</option>{templates.map((t) => <option key={t.sop_template_id} value={t.sop_template_id}>{planName(t.name)}</option>)}</select></label>
      {versions.length !== 1 && <label>{t("Plan edition")}<select value={versionId} onChange={selectVersion} required disabled={busy || !templateId}><option value="">{t("Choose edition")}</option>{versions.map((v) => <option key={v.sop_version_id} value={v.sop_version_id}>{t("Edition ")}{v.version_number}</option>)}</select></label>}
      {preview && <div><h3>{t("Plan preview")}</h3><ol>{preview.tasks.map((task) => <li key={task.sop_task_id}><strong>{task.title}</strong> · {phaseLabel(task.phase, cycle.lifecycle_type)} · {label(task.schedule_type)}{task.offset_days != null ? t(" · {{v0}} days", { v0: task.offset_days }) : t(" · No automatic due date")}{task.crop_stage_key ? ` · ${task.crop_stage_key}` : ""}{task.condition_text ? ` · ${task.condition_text}` : ""}<p>{task.instructions}</p></li>)}</ol></div>}
      <p>{t("Season starts: ")}{displayDate(cycle.period_started_on)}{t(" · Expected harvest: ")}{displayDate(cycle.expected_harvest_on)}</p>
      {!cycle.period_started_on && <p>{t("For a season plan, set Season start under Overview → Season dates first.")}</p>}
      {preview?.tasks.some((t) => ["days_before_planting", "days_after_planting"].includes(t.schedule_type)) && <label>{cycle.status === "planned" ? t("Expected planting date") : t("Actual planting date")}<input type="date" value={anchor} onChange={(e) => setAnchor(e.target.value)} required readOnly={Boolean(cycle.planted_on || cycle.expected_planting_on)} /></label>}
      <p>{t("Dates use each task's schedule: season start, planting or expected harvest. Stage, condition and manual tasks have no automatic due date. Generating a plan does not mark planting as done; saved task dates stay fixed.")}</p>
      <button className="primary-button" disabled={busy || !preview}>{t("Generate Crop Plan")}</button>
    </form></section>;
}

function TaskCard({ task, lifecycle, active, run, busy, api, refresh }) {
  useTranslation();
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const transitions = taskTransitions[task.status] || [];
  return <article className="cm-card"><div className="cm-row"><h3>{task.title}</h3><span className={task.is_overdue ? "cm-overdue" : "cm-badge"}>{task.is_overdue ? t("Overdue · ") : ""}{label(task.status)}</span></div>
    <p>{phaseLabel(task.phase, lifecycle)} · {label(task.task_type)} · {task.due_date ? t("Due {{v0}}", { v0: displayDate(task.due_date) }) : t("No automatic due date")}</p>
    {task.crop_stage_key && <p>{t("Stage: ")}{label(task.crop_stage_key)}</p>}{task.condition_text && <p>{t("When: ")}{task.condition_text}</p>}
    <p className="cm-instructions">{task.instructions}</p>
    {task.status_note && <p className="cm-note">{task.status_note}</p>}
    {task.completed_at && <p>{t("Completed ")}{new Date(task.completed_at).toLocaleString("en-IN")}</p>}
    {active && transitions.length > 0 && <details><summary>{t("Update task / Complete")}</summary><form onInvalid={revealInvalidField} className="cm-form" onSubmit={(event) => { event.preventDefault(); run(async () => { await api(`/my/crop-tasks/${task.crop_task_id}/status`, "POST", { expected_status: task.status, status, status_note: note.trim() || null }); await refresh(); }); }}>
      <div className="cm-row" role="group" aria-label={t("Task action")}>{transitions.map((value) => <button key={value} type="button" aria-pressed={status === value} onClick={() => setStatus(value)}>{taskActionLabel(value)}</button>)}</div>
      <label>{t("Note")}{["partial", "not_applicable", "cancelled"].includes(status) ? t(" (required)") : t(" (optional)")}<textarea value={note} onChange={(e) => setNote(e.target.value)} required={["partial", "not_applicable", "cancelled"].includes(status)} /></label>
      <button disabled={busy || !status}>{t("Confirm task update")}</button></form></details>}
  </article>;
}

function CycleDetail({ id, api, run, busy, onFarms, onOpen, token, onViewBooking, onMarketplace, initialTab, onShareUpdate }) {
  useTranslation();
  const [tab, setTab] = useState(initialTab || "overview");
  const [bookTask, setBookTask] = useState(null);
  const [confirmWork, setConfirmWork] = useState(null);
  const [bookExpense, setBookExpense] = useState(null);
  const [serviceRevision, setServiceRevision] = useState(0);
  useEffect(() => { if (bookTask || confirmWork || bookExpense) document.getElementById("crop-task-service-form")?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [bookTask, confirmWork, bookExpense]);
  const [recordTask, setRecordTask] = useState(null);
  const [savedRecord, setSavedRecord] = useState(null);
  const [shareableRecord, setShareableRecord] = useState(null);
  const [cycle, setCycle] = useState(null);
  const [error, setError] = useState("");
  const [nextStatus, setNextStatus] = useState("");
  const [planted, setPlanted] = useState("");
  const [note, setNote] = useState("");
  const refresh = useCallback(async () => { const data = await api(`/my/crop-cycles/${id}`); setCycle(data); setError(""); setNextStatus(""); }, [api, id]);
  useEffect(() => { let active = true; api(`/my/crop-cycles/${id}`).then((data) => { if (active) setCycle(data); }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, id]);
  if (!cycle) return <section className="cm-card">{error ? <><p role="alert">{messageText(error)}</p><button onClick={() => run(refresh)}>{t("Retry")}</button></> : t("Loading crop...")}</section>;
  const options = cycle.status === "planned" ? ["active", "cancelled"] : cycle.status === "active" ? ["cancelled"] : [];
  const current = ["planned", "active"].includes(cycle.status);
  const context = { farm_id: cycle.farm_id, plot_id: cycle.plot_id, farm_block_id: cycle.farm_block_id, farm_crop_id: id };
  function shareUpdate() {
    // Only public identity/display fields cross into the composer handoff.
    const publicContext = {};
    if (Number.isSafeInteger(cycle.farm_id) && cycle.farm_id > 0 && typeof cycle.farm_name === "string" && cycle.farm_name.trim()) {
      publicContext.farm = { canonicalFarmId: cycle.farm_id, name: cycle.farm_name.trim() };
    }
    if (Number.isSafeInteger(cycle.crop_id) && cycle.crop_id > 0 && typeof cycle.crop_name === "string" && cycle.crop_name.trim()) {
      publicContext.crop = { canonicalCropId: cycle.crop_id, name: cycle.crop_name.trim() };
    }
    onShareUpdate(publicContext);
  }

  return <><header className="cm-crop-context"><h2>{cycle.crop_name}</h2><p>{[cycle.farm_name, cycle.plot_name, cycle.block_name].filter(Boolean).join(" · ")} · {cropStatusLabel(cycle)}</p>{!current && <p>{t("Crop history. Saved work, costs, inputs and field records remain available.")}</p>}</header>
  <nav className="cm-tabs cm-tabs-harvest" aria-label={t("Crop workspace")}>{[["overview", "Overview"], ["plan", "Crop Plan"], ["activities", "Activities"], ["expenses", "Expenses"], ["harvests", "Harvests"]].map(([key, title]) => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>{title}</button>)}</nav>
  {tab === "overview" && <><section className="cm-card"><div className="cm-row"><h2>{cycle.crop_name}</h2><button disabled={busy} onClick={() => run(refresh)}>{t("Update crop details")}</button></div><CycleSummary cycle={cycle} />
    <PlantingSummary cycle={cycle} />
    {!cycle.plan && current && <div className="cm-row"><button onClick={() => setTab("activities")}>{t("Track Myself")}</button><button onClick={() => setTab("plan")}>{t("Use Crop Plan")}</button></div>}
    {cycle.plan?.season_date_mismatch && <p className="cm-note">{t("Season dates have changed since this plan was generated. Saved task dates remain unchanged.")}</p>}
    {cycle.plan?.planting_date_mismatch && <p className="cm-note">{t("Actual planting differs from the expected planting date used for this plan (")}{displayDate(cycle.plan.anchor_date)}{t("). Task dates remain unchanged.")}</p>}
    {options.length > 0 && <details><summary>{cycle.status === "planned" ? t("Record planting / Cancel crop") : t("Cancel crop")}</summary><form onInvalid={revealInvalidField} className="cm-form" onSubmit={(event) => { event.preventDefault(); run(async () => { await api(`/my/crop-cycles/${id}/status`, "POST", { expected_status: cycle.status, status: nextStatus, ...(nextStatus === "active" ? { planted_on: planted } : {}), note: note.trim() || null }); await refresh(); }); }}>
      <label>{t("What happened?")}<select value={nextStatus} onChange={(e) => setNextStatus(e.target.value)} required><option value="">{t("Choose action")}</option>{options.map((value) => <option key={value} value={value}>{value === "active" ? t("Planting completed") : t("Cancel this crop")}</option>)}</select></label>
      {nextStatus === "active" && <label>{t("Actual planting date")}<input type="date" value={planted} onChange={(e) => setPlanted(e.target.value)} required /></label>}
      {nextStatus === "cancelled" && <label>{t("Cancellation reason")}<textarea value={note} onChange={(e) => setNote(e.target.value)} required /></label>}
      {nextStatus === "harvested" && <p>{t("Unfinished tasks will be cancelled with a harvest explanation. Completed tasks and all task history remain available.")}</p>}
      <button disabled={busy}>{t("Save change")}</button>
    </form></details>}
  </section>
  <CompletionReview key={`${id}-${cycle.perennial_planting_id || "single"}`} api={api} cycle={cycle} onChanged={refresh} />
  <SeasonDates key={`${cycle.farm_crop_id}-${cycle.updated_at}`} api={api} cycle={cycle} refresh={refresh} run={run} busy={busy} />
  <SeasonPanel api={api} cycle={cycle} onChanged={refresh} onOpen={onOpen} />
  <OverviewRecords api={api} id={id} onTab={setTab} />
  <FarmerFieldWork api={api} cycleId={id} /></>}
  {tab === "overview" && options.length > 0 && !cycle.perennial_planting_id && <PlantingEdit key={cycle.updated_at || id} api={api} cycle={cycle} onSaved={refresh} />}
  {tab === "plan" && <>
    <div id="crop-task-service-form" />
    {bookTask && <TaskServiceBooking api={api} token={token} task={bookTask} onCancel={() => setBookTask(null)} onMarketplace={onMarketplace} onDone={async () => { setBookTask(null); setServiceRevision((n) => n + 1); await refresh(); }} />}
    {confirmWork && <ActivityForm key={confirmWork.booking.booking_id} api={api} context={context} task={confirmWork.task} booking={confirmWork.booking} onCancel={() => setConfirmWork(null)} onSaved={(saved) => { setSavedRecord(saved); setConfirmWork(null); setServiceRevision((n) => n + 1); setTab("activities"); }} />}
    {bookExpense && <ExpenseForm key={bookExpense.booking.booking_id} api={api} context={context} activity={bookExpense.activity} suggestedAmount={bookExpense.booking.total_amount} onCancel={() => setBookExpense(null)} onSaved={(saved) => { setSavedRecord(saved); setBookExpense(null); setServiceRevision((n) => n + 1); setTab("expenses"); }} />}

    {!cycle.plan && options.length > 0 && <PlanSetup key={cycle.status} api={api} cycle={cycle} run={run} busy={busy} refresh={refresh} onFarms={onFarms} />}
    {recordTask && current && <ActivityForm key={recordTask.crop_task_id} api={api} context={context} task={recordTask} onSaved={(saved) => { setSavedRecord(saved); setShareableRecord(saved); setRecordTask(null); setTab("activities"); }} onCancel={() => setRecordTask(null)} />}
    {cycle.plan && <section><h2>{planName(cycle.plan.sop_template_name_snapshot)}</h2><details><summary>{t("Plan details")}</summary><p>{t("Edition ")}{cycle.plan.sop_version_number_snapshot}{t(" · Season start: ")}{displayDate(cycle.plan.season_start_snapshot)}{t(" / Planting reference: ")}{displayDate(cycle.plan.anchor_date)}</p></details><h3>{t("Planned tasks")}</h3>{cycle.status === "planned" && <p>{t("Season tasks can be recorded before planting. Some older plan tasks become available after planting.")}</p>}{cycle.plan.tasks.map((task) => <div key={`${task.crop_task_id}-${task.status}`} id={`crop-task-${task.crop_task_id}`}><TaskCard task={task} lifecycle={cycle.lifecycle_type} active={cycle.status === "active" || (cycle.status === "planned" && !!task.phase)} run={run} busy={busy} api={api} refresh={refresh} />{current && <button disabled={!!bookTask || !!confirmWork || !!bookExpense} onClick={() => setRecordTask(task)}>{t("Record Work · ")}{task.title}</button>}<TaskServiceActions api={api} task={task} cycle={cycle} revision={serviceRevision} busy={busy || !!bookTask || !!confirmWork || !!bookExpense} onBook={() => { setRecordTask(null); setBookTask(task); }} onView={onViewBooking} onConfirm={(booking) => { setRecordTask(null); setConfirmWork({ task, booking }); }} onExpense={(booking) => run(async () => { const activity = await api(`/my/farm-activities/${booking.activity_id}`); setBookExpense({ booking, activity }); })} onComplete={() => run(async () => { await api(`/my/crop-tasks/${task.crop_task_id}/status`, "POST", { expected_status: task.status, status: "completed", status_note: "Farmer confirmed recorded service work." }); await refresh(); })} /></div>)}</section>}
    {!cycle.plan && !options.length && <p>{t("No crop plan was generated for this closed crop. Activity and expense history are still available.")}</p>}
  </>}
  {tab === "harvests" && <CropHarvests api={api} cycleId={id} history={!current} />}
  {["activities", "expenses"].includes(tab) && <FarmLedger key={tab} initialSavedAction={tab === "activities" && savedRecord && savedRecord === shareableRecord && onShareUpdate ? <button type="button" onClick={shareUpdate}>{t("Share this update")}</button> : null} initialSaved={savedRecord && (tab === "activities" ? savedRecord.description : savedRecord.expense_id) ? savedRecord : null} api={api} context={context} mode={tab} history={!current} onTask={(taskId) => { setTab("plan"); setTimeout(() => document.getElementById(`crop-task-${taskId}`)?.scrollIntoView({ behavior: "smooth" }), 0); }} />}
  </>;
}

export default function CropManagement({ token, backLabel = "Marketplace", onBack, onFarms, farmerId, initialCycleId, initialContext, onContextConsumed, onShareUpdate }) {
  useTranslation();
  const api = useCropApi(token);
  const [cycles, setCycles] = useState([]);
  const [farms, setFarms] = useState([]);
  const [crops, setCrops] = useState([]);
  const [catalogueReady, setCatalogueReady] = useState(false);
  const [selected, setSelected] = useState(initialCycleId || null);
  const [viewBooking, setViewBooking] = useState(null);
  const [returnToPlan, setReturnToPlan] = useState(!!initialCycleId);
  const [adding, setAdding] = useState(!!initialContext);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState("current");
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const list = await api(`/my/crop-cycles?view=${view}&limit=20&offset=${offset}`);
        if (active) { setCycles(list); setError(""); }
      } catch (err) { if (active) setError(err.message); }
      finally { if (active) setLoading(false); }
    }
    load(); return () => { active = false; };
  }, [api, offset, view, attempt]);
  useEffect(() => {
    let active = true;
    Promise.all([api("/my/farms"), api("/crops")]).then(([farmData, cropData]) => { if (active) { setFarms(farmData); setCrops(cropData); setCatalogueReady(true); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, attempt]);
  async function run(work) {
    if (busy) return;
    setBusy(true); setError("");
    try { await work(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  if (viewBooking != null) return <MyBookings token={token} farmerId={farmerId} initialBookingId={viewBooking} onBack={() => { setViewBooking(null); setReturnToPlan(true); }} onOpenCrop={(id) => { setSelected(id); setReturnToPlan(true); setViewBooking(null); }} />;
  return <main className="cm-page"><div className="cm-content">
    <header className="cm-row"><button onClick={() => { if (selected || adding) { setSelected(null); setAdding(false); onContextConsumed?.(); setAttempt((n) => n + 1); } else onBack(); }}>← {selected || adding ? t("My Crops") : t(backLabel)}</button><h1>{t("My Crops")}</h1></header>
    {error && <div className="cm-error" role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Refresh list")}</button></div>}
    {selected ? <CycleDetail onShareUpdate={onShareUpdate} key={selected} id={selected} token={token} initialTab={returnToPlan ? "plan" : "overview"} onViewBooking={setViewBooking} onMarketplace={onBack} api={api} run={run} busy={busy} onFarms={onFarms} onOpen={(id) => { setReturnToPlan(false); setSelected(id); }} /> : adding && !catalogueReady ? <p>{t("Loading farms and crops...")}</p> : adding ? <NewCycle initialContext={initialContext} api={api} farms={farms} crops={crops} onFarms={onFarms} run={run} busy={busy} onCreated={(cycle, tracking) => { setReturnToPlan(tracking === "plan"); onContextConsumed?.(); setAdding(false); setView("current"); setSelected(cycle.farm_crop_id); }} /> : <>
      <nav className="cm-tabs cm-tabs-pair" aria-label={t("My Crops views")}>{["current", "history"].map((key) => <button key={key} aria-pressed={view === key} onClick={() => { if (key !== view) { setLoading(true); setView(key); setOffset(0); setCycles([]); } }}>{key === "current" ? t("Current") : t("History")}</button>)}</nav>
      <div className="cm-row"><p>{view === "current" ? t("Your growing and planned crops.") : t("Your previous crops and their records.")}</p><button className="primary-button" onClick={() => setAdding(true)} disabled={loading || !catalogueReady}>{t("+ Start Crop")}</button></div>
      {loading ? <p>{t("Loading crops...")}</p> : !cycles.length ? <section className="cm-card"><h2>{view === "current" ? t("No current crops") : t("No crop history")}</h2><p>{view === "current" ? t("Start a crop on a saved plot. You can track work yourself or choose a crop plan.") : t("Harvested and cancelled crops appear here with their saved records.")}</p></section> : cycles.map((cycle) => <CropListCard key={cycle.farm_crop_id} cycle={cycle} history={view === "history"} onOpen={() => { setReturnToPlan(false); setSelected(cycle.farm_crop_id); }} />)}
      {view === "current" && <PerennialPlantings api={api} onOpen={setSelected} />}
      <nav className="cm-row" aria-label={t("Crop pages")}><button disabled={!offset || loading} onClick={() => setOffset((n) => n - 20)}>{t("Previous")}</button><span>{t("Page ")}{offset / 20 + 1}</span><button disabled={cycles.length < 20 || loading} onClick={() => setOffset((n) => n + 20)}>{t("Next")}</button></nav>
    </>}
  </div></main>;
}
