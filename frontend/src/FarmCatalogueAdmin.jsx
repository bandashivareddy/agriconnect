import { useEffect, useState } from "react";
import { label, useCropApi } from "./cropApi";
import { CatalogueSearch } from "./CropInputs";
import "./CropManagement.css";

const configs = {
  "crop-varieties": { title: "Crop varieties", id: "crop_variety_id", name: "variety_name", fields: {
    variety_name: "required", variety_type: ["hybrid", "open_pollinated", "cultivar", "clone", "local", "other"],
    duration_min_days: "number", duration_max_days: "number", days_to_first_harvest_min: "number", days_to_first_harvest_max: "number", notes: "text",
  } },
  "planting-material-sources": { title: "Planting material sources", id: "planting_material_source_id", name: "source_name", fields: {
    source_name: "required", brand_name: "string", source_type: ["seed_company", "nursery", "tissue_culture_supplier", "farmer_saved", "local_supplier", "other"], notes: "text",
  } },
  "farm-input-products": { title: "Farm input products", id: "farm_input_product_id", name: "product_name", fields: {
    product_name: "required", input_type: ["fertilizer", "pesticide", "fungicide", "herbicide", "bio_input", "growth_regulator", "soil_amendment", "micronutrient", "other"], brand_name: "string", manufacturer_name: "string", active_ingredient: "text", formulation: "string", nutrient_composition: "json", default_unit: ["kg", "g", "L", "ml", "tonne", "unit"], notes: "text",
  } },
};

function MasterForm({ api, kind, initial, onSaved, onCancel }) {
  const config = configs[kind];
  const [form, setForm] = useState(() => ({ ...(initial || {}), nutrient_composition: initial?.nutrient_composition ? JSON.stringify(initial.nutrient_composition, null, 2) : "", status: initial?.status || "active" }));
  const [choosing, setChoosing] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    try {
      const data = Object.fromEntries(Object.entries(config.fields).map(([k, type]) => [k, type === "number" ? (form[k] ? Number(form[k]) : null) : type === "json" ? (form[k] ? JSON.parse(form[k]) : null) : form[k] || null]));
      data.status = form.status;
      if (kind === "crop-varieties") { data.crop_id = Number(form.crop_id); data.default_planting_material_source_id = form.default_planting_material_source_id || null; }
      await api(`/admin/${kind}${initial ? `/${initial[config.id]}` : ""}`, initial ? "PUT" : "POST", { ...data, ...(initial ? { expected_updated_at: initial.updated_at } : {}) }); onSaved();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <form className="cm-form cm-card" onSubmit={submit}><h2>{initial ? "Edit" : "Create"} {config.title}</h2>{error && <p className="cm-error" role="alert">{error}</p>}
    {kind === "crop-varieties" && <><p>Crop: {form.crop_name || (form.crop_id ? `#${form.crop_id}` : "Select a crop")}</p>{!initial && <button type="button" onClick={() => setChoosing("crop")}>Choose crop</button>}{choosing === "crop" && <CatalogueSearch api={api} path="/catalogue/crops" title="crops" idKey="crop_id" nameKey="crop_name" onSelect={(c) => { setForm({ ...form, crop_id: c.crop_id, crop_name: c.crop_name }); setChoosing(null); }} />}
      <p>Default material source: {form.source_name || form.default_planting_material_source_id || "None"}</p><div className="cm-row"><button type="button" onClick={() => setChoosing("source")}>Choose default source</button><button type="button" onClick={() => setForm({ ...form, default_planting_material_source_id: null, source_name: null })}>Clear default</button></div>{choosing === "source" && <CatalogueSearch api={api} path="/catalogue/planting-material-sources" title="sources" idKey="planting_material_source_id" nameKey="source_name" onSelect={(s) => { setForm({ ...form, default_planting_material_source_id: s.planting_material_source_id, source_name: s.source_name }); setChoosing(null); }} />}
      <p>Duration and first-harvest values are separate optional estimates. Leave unknown/perennial durations blank.</p></>}
    {Object.entries(config.fields).map(([key, type]) => <label key={key}>{label(key)}{type === "required" || ["source_type", "input_type"].includes(key) ? " (required)" : " (optional)"}
      {Array.isArray(type) ? <select value={form[key] || ""} required={["source_type", "input_type"].includes(key)} onChange={(e) => setForm({ ...form, [key]: e.target.value })}><option value="">Not specified</option>{type.map((v) => <option key={v} value={v}>{label(v)}</option>)}</select> : ["text", "json"].includes(type) ? <textarea value={form[key] || ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /> : <input value={form[key] ?? ""} type={type === "number" ? "number" : "text"} min={type === "number" ? 1 : undefined} max={type === "number" ? 36500 : undefined} maxLength={type === "number" ? undefined : 200} required={type === "required"} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />}
    </label>)}
    {kind === "farm-input-products" && <p>Composition is optional JSON containing labelled percentages, e.g. {"{\"N\":19,\"P2O5\":19,\"K2O\":19}"}. Store only values on the label; do not infer chemistry. No price or recommended dose is recorded.</p>}
    <label>Status<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
    <div className="cm-row"><button type="button" disabled={busy} onClick={onCancel}>Cancel</button><button disabled={busy || (kind === "crop-varieties" && !form.crop_id)} className="primary-button">Save catalogue entry</button></div>
  </form>;
}

export function CropMetadataForm({ api }) {
  const [crop, setCrop] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [revision, setRevision] = useState(0);
  async function create(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setMessage("");
    try {
      const saved = await api("/admin/crops", "POST", { crop_name: name.trim() });
      setCrop(saved); setAdding(false); setName(""); setRevision((n) => n + 1);
      setMessage("Crop created. Configure its metadata below.");
    } catch (err) { setMessage(err.message); } finally { setBusy(false); }
  }
  async function save(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setMessage("");
    try { const updated = await api(`/admin/crops/${crop.crop_id}/metadata`, "PUT", { crop_group: crop.crop_group || null, lifecycle_type: crop.lifecycle_type || null, harvest_pattern: crop.harvest_pattern || null }); setCrop(updated); setMessage("Crop metadata saved."); }
    catch (err) { setMessage(err.message); } finally { setBusy(false); }
  }
  return <section><div className="cm-row"><h2>Crop metadata</h2><button disabled={busy || adding} onClick={() => { setAdding(true); setMessage(""); }}>+ Add Crop</button></div>
    {adding && <form className="cm-form cm-card" onSubmit={create}><h3>Add Crop</h3><label>Crop name<input autoFocus required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} /></label><div className="cm-row"><button disabled={busy || !name.trim()}>Create Crop</button><button type="button" disabled={busy} onClick={() => setAdding(false)}>Cancel</button></div></form>}
    <CatalogueSearch key={revision} api={api} path="/catalogue/crops" title="crops" idKey="crop_id" nameKey="crop_name" onSelect={(c) => { setCrop(c); setMessage(""); }} />{message && <p role="status">{message}</p>}{crop && <form className="cm-form cm-card" onSubmit={save}><h2>{crop.crop_name}</h2>{Object.entries({ crop_group: ["orchard", "seasonal", "vegetable"], lifecycle_type: ["seasonal", "perennial"], harvest_pattern: ["single", "multiple", "recurring"] }).map(([key, choices]) => <label key={key}>{label(key)} (optional)<select value={crop[key] || ""} onChange={(e) => setCrop({ ...crop, [key]: e.target.value })}><option value="">Not classified</option>{choices.map((v) => <option key={v}>{v}</option>)}</select></label>)}<p>Choose Perennial for a continuing planting that can have multiple seasons.</p><button disabled={busy}>Save crop metadata</button></form>}</section>;
}

export default function FarmCatalogueAdmin({ token, onBack }) {
  const api = useCropApi(token);
  const [kind, setKind] = useState("crop-varieties");
  const [query, setQuery] = useState("");
  const [cropFilter, setCropFilter] = useState(null);
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (kind === "crop-metadata") return;
    let active = true;
    const timer = setTimeout(async () => {
      setLoading(true); setError("");
      try { const data = await api(`/admin/${kind}?q=${encodeURIComponent(query)}&offset=${offset}${kind === "crop-varieties" && cropFilter ? `&crop_id=${cropFilter.crop_id}` : ""}`); if (active) setItems(data); }
      catch (err) { if (active) setError(err.message); } finally { if (active) setLoading(false); }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [api, kind, query, offset, revision, cropFilter]);
  return <main className="cm-page"><div className="cm-content"><header className="cm-row"><button onClick={onBack}>← Admin Dashboard</button><h1>Crop & Input Catalogue</h1></header><nav className="cm-row">{[...Object.keys(configs), "crop-metadata"].map((key) => <button key={key} onClick={() => { setKind(key); setForm(null); setOffset(0); setItems([]); }}>{configs[key]?.title || "Crop metadata"}</button>)}</nav>
    {kind === "crop-metadata" ? <CropMetadataForm api={api} /> : <>
      <h2>{configs[kind].title}</h2><label>Search<input maxLength={200} value={query} onChange={(e) => { setQuery(e.target.value); setOffset(0); }} /></label>
      {kind === "crop-varieties" && <details><summary>Filter by crop {cropFilter ? `· ${cropFilter.crop_name}` : ""}</summary><button onClick={() => { setCropFilter(null); setOffset(0); }}>All crops</button><CatalogueSearch api={api} path="/catalogue/crops" title="crop filter" idKey="crop_id" nameKey="crop_name" onSelect={(c) => { setCropFilter(c); setOffset(0); }} /></details>}
      {error && <p role="alert">{error} <button onClick={() => setRevision((n) => n + 1)}>Retry</button></p>}
      <button onClick={() => setForm({ initial: null })}>+ Create entry</button>{form && <MasterForm key={`${kind}-${form.initial?.[configs[kind].id] || "new"}`} api={api} kind={kind} initial={form.initial} onCancel={() => setForm(null)} onSaved={() => { setForm(null); setRevision((n) => n + 1); }} />}
      {loading ? <p>Loading…</p> : items.map((item) => <article className="cm-card" key={item[configs[kind].id]}><h3>{item[configs[kind].name]}</h3><p>{item.status}{item.crop_id ? ` · Crop #${item.crop_id}` : ""}{item.brand_name ? ` · ${item.brand_name}` : ""}</p>{item.active_ingredient && <p>Active ingredient: {item.active_ingredient} · {item.formulation}</p>}<button onClick={() => setForm({ initial: item })}>Edit / deactivate</button></article>)}
      <div className="cm-row"><button disabled={!offset || loading} onClick={() => setOffset(offset - 20)}>Previous</button><button disabled={items.length < 20 || loading} onClick={() => setOffset(offset + 20)}>Next</button></div>
    </>}
  </div></main>;
}
