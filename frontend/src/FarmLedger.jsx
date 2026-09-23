import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { revealInvalidField } from "./farmerUx";
import { useEffect, useState } from "react";
import { displayDate, label } from "./cropApi";
import { InputDraft, InputHistory } from "./CropInputs";

const activityTypes = ["land_preparation", "sowing_planting", "irrigation", "fertilizer", "pesticide", "weed_management", "labour", "machinery", "pruning", "inspection", "harvest_support", "transport", "repair", "other"];
const categories = ["seed_planting_material", "fertilizer", "pesticide", "labour", "irrigation", "diesel_fuel", "machinery", "repair", "transport", "harvesting", "packing", "electricity", "miscellaneous"];
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const money = (value) => Number(value).toLocaleString("en-IN", { style: "currency", currency: "INR" });

export function ActivityForm({ api, context, task, booking, visitId, officer = false, initial, onSaved, onCancel }) {
  useTranslation();
  const [inputs, setInputs] = useState([]);
  const [addingInput, setAddingInput] = useState(false);
  const [form, setForm] = useState(initial || { activity_type: task && activityTypes.includes(task.task_type) ? task.task_type : "other", activity_date: today(), description: task?.title || "", quantity: "", unit: "", notes: "" });
  const [requestKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function field(e) { setForm((old) => ({ ...old, [e.target.name]: e.target.value })); }
  async function save(e) {
    e.preventDefault(); if (busy) return; if (addingInput) { setError("Add or cancel the unfinished input before saving this activity."); return; } setBusy(true); setError("");
    const data = { activity_type: form.activity_type, activity_date: form.activity_date, description: form.description.trim() || (!officer && form.activity_type !== "other" ? label(form.activity_type) : ""), quantity: form.quantity || null, unit: form.unit || null, notes: form.notes || null, performed_by_user_id: initial?.performed_by_user_id || null };
    const base = officer ? `/field-work/crop-cycles/${context.farm_crop_id}/activities` : "/my/farm-activities";
    const path = initial ? `${base}/${initial.activity_id}` : task && !officer && !booking ? `/my/crop-tasks/${task.crop_task_id}/record-work` : base;
    try {
      const saved = await api(path, initial ? "PUT" : "POST", initial ? { ...data, expected_updated_at: initial.updated_at } : { ...data, ...context, inputs: inputs.map((i) => i.payload), request_key: requestKey, service_booking_id: booking?.booking_id || null, source_type: booking ? "service_booking" : visitId ? "field_visit" : task ? "crop_task" : "manual", crop_task_id: task?.crop_task_id || null, field_visit_id: visitId || null });
      onSaved(saved);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <form onInvalid={revealInvalidField} className="cm-form cm-card" onSubmit={save}><h3>{initial ? t("Edit Activity") : task ? t("Record Work: {{v0}}", { v0: task.title }) : t("Add Activity")}</h3>
    <p>{t("Record work that actually happened. This does not change a task status, record field verification, or create an expense.")}</p>
    {error && <p className="cm-error" role="alert">{messageText(error)}</p>}
    <label>{t("Activity type")}<select name="activity_type" value={form.activity_type} onChange={field}>{activityTypes.map((v) => <option key={v} value={v}>{label(v)}</option>)}</select></label>
    <label>{t("Date")}<input type="date" name="activity_date" value={form.activity_date} onChange={field} required /></label>
    <label>{t("Work performed")}{!officer && form.activity_type !== "other" ? t(" (optional detail)") : ""}<textarea name="description" value={form.description} placeholder={form.activity_type !== "other" ? label(form.activity_type) : t("What work was done?")} onChange={field} required={officer || form.activity_type === "other"} /></label>
    <details><summary>{t("Quantity and notes (optional)")}</summary><label>{t("Quantity (optional)")}<input type="number" min="0.0001" step="0.0001" name="quantity" value={form.quantity ?? ""} onChange={field} /></label>
    <label>{t("Unit ")}{form.quantity ? t("(required)") : t("(optional)")}<input name="unit" value={form.unit ?? ""} onChange={field} maxLength={50} required={Boolean(form.quantity)} placeholder={t("hours, kg, litres…")} /></label>
    <label>{t("Notes")}<textarea name="notes" value={form.notes ?? ""} onChange={field} /></label></details>
    {!initial && <section><h3>{t("Actual inputs used (optional)")}</h3>{inputs.map((i, index) => <article className="cm-card" key={index}><p>{i.name} · {i.payload.quantity} {i.payload.unit}</p><button type="button" onClick={() => setInputs(inputs.filter((_, n) => n !== index))}>{t("Remove draft input")}</button></article>)}<button type="button" disabled={busy || inputs.length >= 50} onClick={() => setAddingInput(true)}>{t("+ Add Input")}</button>{addingInput && <InputDraft api={api} onCancel={() => setAddingInput(false)} onSave={(payload, product) => { setInputs([...inputs, { payload, name: product.product_name }]); setAddingInput(false); }} />}</section>}
    <div className="cm-row"><button type="button" disabled={busy} onClick={onCancel}>{t("Cancel")}</button><button className="primary-button" disabled={busy || addingInput}>{busy ? t("Saving…") : t("Save Activity")}</button></div>
  </form>;
}

export function ExpenseForm({ api, context, activity, activities = [], suggestedAmount, initial, onSaved, onCancel }) {
  useTranslation();
  const [form, setForm] = useState(initial || { expense_date: today(), category: "miscellaneous", amount: suggestedAmount ?? "", vendor_person: "", payment_mode: "", notes: "", activity_id: activity?.activity_id || "" });
  const [requestKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function field(e) { setForm((old) => ({ ...old, [e.target.name]: e.target.value })); }
  async function save(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    const data = { expense_date: form.expense_date, category: form.category, amount: form.amount, vendor_person: form.vendor_person || null, payment_mode: form.payment_mode || null, notes: form.notes || null };
    const linked = activity || activities.find((a) => a.activity_id === Number(form.activity_id));
    const scope = linked ? { farm_id: linked.farm_id, plot_id: linked.plot_id, farm_block_id: linked.farm_block_id, farm_crop_id: linked.farm_crop_id } : context;
    try { const saved = await api(`/my/farm-expenses${initial ? `/${initial.expense_id}` : ""}`, initial ? "PUT" : "POST", initial ? { ...data, expected_updated_at: initial.updated_at } : { ...data, ...scope, activity_id: form.activity_id ? Number(form.activity_id) : null, request_key: requestKey }); onSaved(saved); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <form onInvalid={revealInvalidField} className="cm-form cm-card" onSubmit={save}><h3>{initial ? t("Edit Expense") : t("Add Expense")}</h3>{error && <p className="cm-error" role="alert">{messageText(error)}</p>}
    <label>{t("Date")}<input type="date" name="expense_date" value={form.expense_date} onChange={field} required /></label>
    <label>{t("Category")}<select name="category" value={form.category} onChange={field}>{categories.map((v) => <option key={v} value={v}>{label(v)}</option>)}</select></label>
    {suggestedAmount != null && <p>{t("Booking amount suggested below. Confirm or correct the actual cost before saving.")}</p>}
    <label>{t("Amount (₹)")}<input type="number" min="0.01" step="0.01" name="amount" value={form.amount} onChange={field} required /></label>
    {activity && <p>{t("For work: ")}{activity.description}</p>}
    {!initial && !activity && <label>{t("Activity (optional)")}<select name="activity_id" value={form.activity_id} onChange={field} disabled={Boolean(activity)}><option value="">{t("Standalone expense")}</option>{(activity ? [activity] : activities).map((a) => <option key={a.activity_id} value={a.activity_id}>{displayDate(a.activity_date)} · {a.description}</option>)}</select></label>}
    <details><summary>{t("Vendor, payment and notes (optional)")}</summary><label>{t("Vendor / person")}<input name="vendor_person" value={form.vendor_person ?? ""} onChange={field} maxLength={200} /></label>
    <label>{t("Payment mode")}<input name="payment_mode" value={form.payment_mode ?? ""} onChange={field} maxLength={50} placeholder={t("Cash, UPI, bank transfer…")} /></label>
    <label>{t("Notes")}<textarea name="notes" value={form.notes ?? ""} onChange={field} /></label></details>
    <div className="cm-row"><button type="button" disabled={busy} onClick={onCancel}>{t("Cancel")}</button><button className="primary-button" disabled={busy}>{busy ? t("Saving…") : t("Save Expense")}</button></div>
  </form>;
}

export default function FarmLedger({ api, context, mode = "activities", onTask, history = false, initialSaved = null, initialSavedAction = null }) {
  useTranslation();
  const [manageHistory, setManageHistory] = useState(false);
  const [savedRecord, setSavedRecord] = useState(initialSaved);
  const allowEdits = !history || manageHistory;
  const [data, setData] = useState(null);
  const [activities, setActivities] = useState([]);
  const [form, setForm] = useState(null);
  const [linkedTask, setLinkedTask] = useState(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filters, setFilters] = useState({ date_from: "", date_to: "", kind: "" });
  const scope = JSON.stringify(context);
  useEffect(() => {
    let active = true;
    async function load() {
      setError(""); setData(null);
      const query = new URLSearchParams(Object.entries(JSON.parse(scope)).filter(([, v]) => v != null));
      for (const name of ["date_from", "date_to"]) if (filters[name]) query.set(name, filters[name]);
      if (filters.kind) query.set(mode === "activities" ? "activity_type" : "category", filters.kind);
      query.set("offset", offset);
      try {
        const result = await api(`/my/farm-${mode}?${query}`);
        if (active) setData(result);
        if (mode === "expenses" && allowEdits) {
          const choices = new URLSearchParams(Object.entries(JSON.parse(scope)).filter(([, v]) => v != null)); choices.set("limit", "100");
          const options = await api(`/my/farm-activities?${choices}`); if (active) setActivities(options.items);
        }
      } catch (err) { if (active) setError(err.message); }
    }
    load(); return () => { active = false; };
  }, [api, mode, scope, filters, offset, revision, allowEdits]);
  function done(saved) { setForm(null); setSavedRecord(saved); setRevision((n) => n + 1); }
  useEffect(() => { if (savedRecord && !form) document.getElementById("saved-farm-record")?.scrollIntoView({ block: "start", behavior: "smooth" }); }, [savedRecord, form]);
  return <section><h2>{label(mode)}</h2><p>{mode === "activities" ? t("Actual work history, with or without a Crop Plan.") : t("Recorded expenses in INR. No revenue or profit is calculated.")}</p>
    <details><summary>{t("Filter records")}</summary><div className="cm-form"><label>{t("From")}<input type="date" value={filters.date_from} onChange={(e) => { setFilters({ ...filters, date_from: e.target.value }); setOffset(0); }} /></label><label>{t("To")}<input type="date" value={filters.date_to} onChange={(e) => { setFilters({ ...filters, date_to: e.target.value }); setOffset(0); }} /></label>
      <label>{mode === "activities" ? t("Activity type") : t("Category")}<select value={filters.kind} onChange={(e) => { setFilters({ ...filters, kind: e.target.value }); setOffset(0); }}><option value="">{t("All")}</option>{(mode === "activities" ? activityTypes : categories).map((v) => <option key={v} value={v}>{label(v)}</option>)}</select></label></div></details>
    {savedRecord && !form && <article id="saved-farm-record" className="cm-card cm-saved" role="status"><h3>{t("Saved ")}{savedRecord.activity_id && savedRecord.description ? t("work") : t("expense")}</h3><p>{displayDate(savedRecord.activity_date || savedRecord.expense_date)}</p><p>{savedRecord.description || `${label(savedRecord.category)}: ${money(savedRecord.amount)}`}</p>{savedRecord.activity_id && savedRecord.description && <InputHistory api={api} activity={savedRecord} canEdit={allowEdits} />}{savedRecord === initialSaved && initialSavedAction}<button onClick={() => setSavedRecord(null)}>{t("Back to records")}</button></article>}
    {error && <p className="cm-error" role="alert">{messageText(error)} <button onClick={() => setRevision((n) => n + 1)}>{t("Retry")}</button></p>}
    {linkedTask && <article className="cm-card"><h3>{t("Crop Task: ")}{linkedTask.title}</h3><p>{label(linkedTask.status)}{t(" · Due ")}{displayDate(linkedTask.due_date)}</p><p className="cm-instructions">{linkedTask.instructions}</p><button onClick={() => setLinkedTask(null)}>{t("Close task detail")}</button></article>}
    {history && <p>{t("Historical records. ")}<button onClick={() => { setManageHistory(!manageHistory); setForm(null); }}>{manageHistory ? t("Return to viewing") : t("Correct / add historical records")}</button></p>}
    {allowEdits && <button onClick={() => setForm({ kind: mode })}>{t("+ Add ")}{mode === "activities" ? t("Activity") : t("Expense")}</button>}
    {form?.kind === "activities" && <ActivityForm key={form.initial?.activity_id || "new"} api={api} context={context} initial={form.initial} onSaved={done} onCancel={() => setForm(null)} />}
    {form?.kind === "expenses" && <ExpenseForm key={form.initial?.expense_id || form.activity?.activity_id || "new"} api={api} context={context} activities={activities} activity={form.activity} initial={form.initial} onSaved={done} onCancel={() => setForm(null)} />}
    {!data ? <p>{error ? t("History unavailable.") : t("Loading history…")}</p> : <>
      {mode === "expenses" && <p className="cm-note"><strong>{t("Total expense: ")}{money(data.total_amount)}</strong> · {data.count}{t(" records matching these filters (all pages)")}</p>}
      {!data.items.length && <p>{t("No ")}{mode}{t(" recorded for this selection.")}</p>}
      {data.items.map((item) => <article className="cm-card" key={item.activity_id && mode === "activities" ? item.activity_id : item.expense_id}>
        <h3>{mode === "activities" ? item.description : `${label(item.category)} · ${money(item.amount)}`}</h3>
        <p>{displayDate(item.activity_date || item.expense_date)} · {label(item.activity_type || item.payment_mode)}</p>
        {mode === "activities" && <><p>{t("Source: ")}{label(item.source_type)}{item.field_visit_id ? t(" · Visit #{{v0}}", { v0: item.field_visit_id }) : ""}</p>{item.quantity && <p>{item.quantity} {item.unit}</p>}{item.crop_task_id && <button onClick={() => { if (onTask) onTask(item.crop_task_id); else api(`/my/crop-tasks/${item.crop_task_id}`).then(setLinkedTask).catch((err) => setError(err.message)); }}>{t("Crop Task #")}{item.crop_task_id}</button>}</>}
        {item.vendor_person && <p>{item.vendor_person}</p>}{mode === "expenses" && item.activity_id && <p>{t("Activity #")}{item.activity_id}</p>}{item.notes && <p className="cm-instructions">{item.notes}</p>}
        {mode === "activities" && <InputHistory api={api} activity={item} canEdit={allowEdits} />}
        {allowEdits && <div className="cm-row"><button onClick={() => setForm({ kind: mode, initial: item })}>{t("Edit")}</button>{mode === "activities" && <button onClick={() => setForm({ kind: "expenses", activity: item })}>{t("Add Expense")}</button>}</div>}
      </article>)}
      <nav className="cm-row" aria-label={t("{{v0}} pages", { v0: mode })}><button disabled={!offset} onClick={() => setOffset(offset - 20)}>{t("Previous")}</button><span>{t("Page ")}{offset / 20 + 1}</span><button disabled={offset + 20 >= data.count} onClick={() => setOffset(offset + 20)}>{t("Next")}</button></nav>
    </>}
  </section>;
}

export function BlockManager({ api, farmId, plots, plotId, onChange }) {
  useTranslation();
  const [savedId, setSavedId] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => { let active = true; api(`/my/farm-blocks?farm_id=${farmId}${plotId ? `&plot_id=${plotId}` : ""}`).then((data) => { if (active) setBlocks(data); }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, farmId, plotId, revision]);
  useEffect(() => { if (savedId && !form) document.getElementById(`farm-block-${savedId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [blocks, savedId, form]);
  async function save(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    const data = { name: form.name, description: form.description || null, area: form.area || null, area_unit: form.area_unit || null, status: form.status };
    try { const saved = await api(`/my/farm-blocks${form.farm_block_id ? `/${form.farm_block_id}` : ""}`, form.farm_block_id ? "PUT" : "POST", form.farm_block_id ? { ...data, expected_updated_at: form.updated_at } : { ...data, farm_id: farmId, plot_id: Number(form.plot_id) }); setSavedId(saved.farm_block_id); setForm(null); setRevision((n) => n + 1); onChange?.(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="cm-card"><h2>{t("Optional plot blocks")}</h2><p>{t("Use blocks to organize a plot. Crops can also use the whole plot.")}</p>{error && <p role="alert">{messageText(error)}</p>}
    <button disabled={!plots.length} onClick={() => setForm({ name: "", plot_id: plotId || (plots.length === 1 ? plots[0].plot_id : ""), description: "", area: "", area_unit: "", status: "active" })}>{t("+ Add Block")}</button>
    {form && <form onInvalid={revealInvalidField} className="cm-form" onSubmit={save}>
      <label>{t("Plot")}<select required disabled={Boolean(form.farm_block_id || plotId)} value={form.plot_id} onChange={(e) => setForm({ ...form, plot_id: e.target.value })}><option value="">{t("Choose plot")}</option>{plots.map((p) => <option key={p.plot_id} value={p.plot_id}>{p.plot_name}</option>)}</select></label>
      <label>{t("Name")}<input required maxLength={150} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label>{t("Description")}<textarea value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
      <label>{t("Area (optional)")}<input type="number" min="0.0001" step="0.0001" value={form.area || ""} onChange={(e) => setForm({ ...form, area: e.target.value })} /></label><label>{t("Area unit")}<select value={form.area_unit || ""} onChange={(e) => setForm({ ...form, area_unit: e.target.value })} required={Boolean(form.area)}><option value="">{t("Not recorded")}</option>{["acres", "hectares", "square_metres"].map((v) => <option key={v} value={v}>{label(v)}</option>)}</select></label>
      {form.farm_block_id && <label>{t("Status")}<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="active">{t("Active")}</option><option value="inactive">{t("Inactive")}</option></select></label>}<div className="cm-row"><button type="button" onClick={() => setForm(null)}>{t("Cancel")}</button><button disabled={busy}>{t("Save Block")}</button></div>
    </form>}
    {blocks.map((b) => <article id={`farm-block-${b.farm_block_id}`} className={`cm-card ${savedId === b.farm_block_id ? "cm-saved" : ""}`} key={b.farm_block_id}><h3>{b.name}</h3><p>{plots.find((p) => p.plot_id === b.plot_id)?.plot_name} · {label(b.status)}{b.area ? ` · ${b.area} ${label(b.area_unit)}` : ""}</p><button onClick={() => setForm(b)}>{t("Edit / deactivate")}</button></article>)}
  </section>;
}

export function FarmWorkspace({ api, farms, initialFarmId = "", showBlocks = true }) {
  useTranslation();
  const [farmId, setFarmId] = useState(String(initialFarmId || (farms.length === 1 ? farms[0].farm_id : "")));
  const [details, setDetails] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [scope, setScope] = useState({ plot_id: "", farm_block_id: "", farm_crop_id: "" });
  const [mode, setMode] = useState("activities");
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!farmId) return;
    let active = true;
    Promise.all([api(`/my/farms/${farmId}`), api(`/my/farm-blocks?farm_id=${farmId}`)]).then(([farm, savedBlocks]) => { if (active) { setDetails(farm); setBlocks(savedBlocks); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, farmId, revision]);
  const context = { farm_id: Number(farmId), ...Object.fromEntries(Object.entries(scope).map(([k, v]) => [k, v ? Number(v) : null])) };
  return <section><h2>{t("Farm-wide records")}</h2><p>{t("For work or costs that apply across your farm. Manage a particular crop from My Crops.")}</p>{farms.length === 1 ? <p>{t("Farm: ")}{farms[0].farm_name}</p> : <label>{t("Farm")}<select value={farmId} onChange={(e) => { setFarmId(e.target.value); setDetails(null); setScope({ plot_id: "", farm_block_id: "", farm_crop_id: "" }); }}><option value="">{t("Choose farm")}</option>{farms.map((f) => <option key={f.farm_id} value={f.farm_id}>{f.farm_name}</option>)}</select></label>}
    {error && <p role="alert">{messageText(error)}</p>}{details && <>
      {showBlocks && <BlockManager key={farmId} api={api} farmId={Number(farmId)} plots={details.plots} onChange={() => setRevision((n) => n + 1)} />}
      <div className="cm-form"><label>{t("Plot (optional)")}<select value={scope.plot_id} onChange={(e) => setScope({ plot_id: e.target.value, farm_block_id: "", farm_crop_id: "" })}><option value="">{t("Entire farm")}</option>{details.plots.map((p) => <option key={p.plot_id} value={p.plot_id}>{p.plot_name}</option>)}</select></label>
        <label>{t("Block (optional)")}<select value={scope.farm_block_id} onChange={(e) => setScope({ ...scope, farm_block_id: e.target.value, farm_crop_id: "" })}><option value="">{t("All / no specific block")}</option>{blocks.filter((b) => !scope.plot_id || b.plot_id === Number(scope.plot_id)).map((b) => <option key={b.farm_block_id} value={b.farm_block_id}>{b.name} · {b.status}</option>)}</select></label>
      </div><nav className="cm-row"><button onClick={() => setMode("activities")}>{t("Activities")}</button><button onClick={() => setMode("expenses")}>{t("Expenses")}</button></nav>
      <FarmLedger key={`${farmId}-${JSON.stringify(scope)}-${mode}`} api={api} context={context} mode={mode} />
    </>}
  </section>;
}

export function OfficerActivities({ api, cycle, visitId, canRecord = true }) {
  useTranslation();
  const [items, setItems] = useState([]);
  const [adding, setAdding] = useState(false);
  const [revision, setRevision] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api(`/field-work/crop-cycles/${cycle.farm_crop_id}/activities?offset=${offset}`).then((data) => { if (active) { setItems(data); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, cycle.farm_crop_id, offset, revision]);
  const context = { farm_id: cycle.farm_id, plot_id: cycle.plot_id, farm_block_id: cycle.farm_block_id, farm_crop_id: cycle.farm_crop_id };
  return <section><h2>{t("Actual farm activities")}</h2><p>{t("Factual work history is separate from field verification. Farmer expenses are private.")}</p>{error && <p role="alert">{messageText(error)} <button onClick={() => setRevision((n) => n + 1)}>{t("Retry")}</button></p>}
    {canRecord && <button onClick={() => setAdding(true)}>{t("Record Activity")}</button>}
    {adding && canRecord && <ActivityForm api={api} context={context} visitId={visitId} officer onCancel={() => setAdding(false)} onSaved={() => { setAdding(false); setRevision((n) => n + 1); }} />}
    {items.map((a) => <article className="cm-card" key={a.activity_id}><h3>{a.description}</h3><p>{displayDate(a.activity_date)} · {label(a.activity_type)} · {label(a.source_type)}</p>{a.quantity && <p>{a.quantity} {a.unit}</p>}{a.notes && <p>{a.notes}</p>}<InputHistory api={api} activity={a} officer canEdit={a.can_edit_inputs} /></article>)}
    <div className="cm-row"><button disabled={!offset} onClick={() => setOffset(offset - 20)}>{t("Previous")}</button><button disabled={items.length < 20} onClick={() => setOffset(offset + 20)}>{t("Next")}</button></div>
  </section>;
}
