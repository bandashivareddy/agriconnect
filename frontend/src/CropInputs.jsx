import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useState } from "react";
import { displayDate, label } from "./cropApi";

const units = ["kg", "g", "L", "ml", "tonne", "unit"];
const types = ["fertilizer", "pesticide", "fungicide", "herbicide", "bio_input", "growth_regulator", "soil_amendment", "micronutrient", "other"];
const dateAfter = (date, days) => { if (!date || !days) return null; const d = new Date(`${date}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + Number(days)); return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10); };

export function CatalogueSearch({ api, path, idKey, nameKey, title, onSelect }) {
  useTranslation();
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      setLoading(true); setError("");
      try { const data = await api(`${path}${path.includes("?") ? "&" : "?"}q=${encodeURIComponent(query)}&limit=20&offset=${offset}`); if (active) setItems(data); }
      catch (err) { if (active) { setItems([]); setError(err.message); } }
      finally { if (active) setLoading(false); }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [api, path, query, offset, attempt]);
  return <section><label>{t("Search ")}{title}<input value={query} onChange={(e) => { setQuery(e.target.value); setOffset(0); }} maxLength={200} /></label>
    {error && <p role="alert">{messageText(error)} <button type="button" onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}
    {loading ? <p>{t("Searching…")}</p> : <><div className="cm-form">{items.map((item) => <button type="button" key={item[idKey]} onClick={() => onSelect(item)}>{item[nameKey]}{item.brand_name ? ` · ${item.brand_name}` : ""}{item.active_ingredient ? ` · ${item.active_ingredient}` : ""}</button>)}</div>{!items.length && !error && <p>{t("No matching entries. You can leave optional selections blank or use the unlisted option.")}</p>}</>}
    <div className="cm-row"><button type="button" disabled={!offset || loading} onClick={() => setOffset(offset - 20)}>{t("Previous")}</button><button type="button" disabled={items.length < 20 || loading} onClick={() => setOffset(offset + 20)}>{t("Next")}</button></div>
  </section>;
}

export function PlantingFields({ api, cropId, value, onChange, plantingDate, onHarvestSuggestion }) {
  useTranslation();
  const variety = value.variety_details || value.planting_snapshot?.variety;
  const source = value.source_details || value.planting_snapshot?.source;
  const [search, setSearch] = useState(null);
  const [sourceError, setSourceError] = useState("");
  function clearVariety() { onChange({ ...value, crop_variety_id: null, variety_text: "", variety_details: null, planting_snapshot: { ...value.planting_snapshot, variety: null } }); }
  return <details className="cm-card"><summary>{t("Variety, source and lot (optional)")}</summary>
    <p>{t("Variety: ")}{variety?.variety_name || value.variety_text || t("Not recorded")}</p>
    <div className="cm-row"><button type="button" disabled={!cropId} onClick={() => setSearch("variety")}>{t("Search varieties")}</button><button type="button" onClick={() => { clearVariety(); setSearch("unlisted"); }}>{t("Unlisted variety")}</button><button type="button" onClick={clearVariety}>{t("Clear variety")}</button></div>
    {search === "variety" && <CatalogueSearch key={cropId} api={api} path={`/catalogue/crop-varieties?crop_id=${cropId}`} title={t("varieties")} idKey="crop_variety_id" nameKey="variety_name" onSelect={(v) => { onChange({ ...value, crop_variety_id: v.crop_variety_id, variety_text: null, variety_details: v }); setSearch(null); }} />}
    {search === "unlisted" || value.variety_text && <label>{t("Unlisted/local variety name")}<input maxLength={200} value={value.variety_text || ""} onChange={(e) => onChange({ ...value, variety_text: e.target.value, crop_variety_id: null, variety_details: null })} /></label>}
    {variety && <div className="cm-note"><p>{t("Approximate total duration: ")}{variety.duration_min_days || "?"}–{variety.duration_max_days || "?"}{t(" days")}</p><p>{t("Approximate first harvest: ")}{variety.days_to_first_harvest_min || "?"}–{variety.days_to_first_harvest_max || "?"}{t(" days")}</p>
      {plantingDate && <><p>{t("Total-duration window: ")}{displayDate(dateAfter(plantingDate, variety.duration_min_days))} – {displayDate(dateAfter(plantingDate, variety.duration_max_days))}</p><p>{t("First-harvest window: ")}{displayDate(dateAfter(plantingDate, variety.days_to_first_harvest_min))} – {displayDate(dateAfter(plantingDate, variety.days_to_first_harvest_max))}</p>
        {onHarvestSuggestion && <div className="cm-row">{variety.duration_max_days && <button type="button" onClick={() => onHarvestSuggestion(dateAfter(plantingDate, variety.duration_max_days))}>{t("Use total-duration end date")}</button>}{variety.days_to_first_harvest_max && <button type="button" onClick={() => onHarvestSuggestion(dateAfter(plantingDate, variety.days_to_first_harvest_max))}>{t("Use first-harvest end date")}</button>}</div>}
      </>}<p>{t("Estimates only. Your expected harvest date changes only when you enter or explicitly choose a date.")}</p></div>}
    <p>{t("Planting material source: ")}{source?.source_name || t("Not recorded")}{source?.brand_name ? ` · ${source.brand_name}` : ""}</p>
    {sourceError && <p role="alert">{messageText(sourceError)}</p>}
    {variety?.default_planting_material_source_id && <button type="button" onClick={async () => { try { const s = await api(`/catalogue/planting-material-sources/${variety.default_planting_material_source_id}`); onChange({ ...value, planting_material_source_id: s.planting_material_source_id, source_details: s }); setSourceError(""); } catch (err) { setSourceError(err.message); } }}>{t("Use variety’s default source")}</button>}
    <div className="cm-row"><button type="button" onClick={() => setSearch("source")}>{t("Search sources")}</button><button type="button" onClick={() => onChange({ ...value, planting_material_source_id: null, source_details: null, planting_snapshot: { ...value.planting_snapshot, source: null } })}>{t("Clear source")}</button></div>
    {search === "source" && <CatalogueSearch api={api} path="/catalogue/planting-material-sources" title={t("sources / brands")} idKey="planting_material_source_id" nameKey="source_name" onSelect={(s) => { onChange({ ...value, planting_material_source_id: s.planting_material_source_id, source_details: s }); setSearch(null); }} />}
    <label>{t("Seed / material lot or batch")}<input value={value.seed_or_material_lot || ""} maxLength={150} onChange={(e) => onChange({ ...value, seed_or_material_lot: e.target.value })} /></label>
  </details>;
}

export function PlantingSummary({ cycle }) {
  useTranslation();
  const v = cycle.planting_snapshot?.variety;
  const s = cycle.planting_snapshot?.source;
  return <div>{v && <p>{t("Variety: ")}<strong>{v.variety_name}</strong>{v.unlisted ? t(" (farmer-entered)") : ""}{v.variety_type ? ` · ${label(v.variety_type)}` : ""}</p>}{s && <p>{t("Planting source: ")}{s.source_name}{s.brand_name ? ` · ${s.brand_name}` : ""}</p>}{cycle.seed_or_material_lot && <p>{t("Lot / batch: ")}{cycle.seed_or_material_lot}</p>}{v?.duration_min_days || v?.duration_max_days ? <p>{t("Approximate total duration: ")}{v.duration_min_days || "?"}–{v.duration_max_days || "?"}{t(" days")}</p> : null}{v?.days_to_first_harvest_min || v?.days_to_first_harvest_max ? <p>{t("Approximate first harvest: ")}{v.days_to_first_harvest_min || "?"}–{v.days_to_first_harvest_max || "?"}{t(" days")}</p> : null}</div>;
}

export function PlantingEdit({ api, cycle, onSaved }) {
  useTranslation();
  const [value, setValue] = useState(cycle);
  const [harvest, setHarvest] = useState(cycle.expected_harvest_on || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    try { await api(`/my/crop-cycles/${cycle.farm_crop_id}`, "PATCH", { crop_variety_id: value.crop_variety_id || null, planting_material_source_id: value.planting_material_source_id || null, variety_text: value.variety_text || null, seed_or_material_lot: value.seed_or_material_lot || null, expected_harvest_on: harvest || null }); await onSaved(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <details className="cm-card"><summary>{t("Edit planting details / expected harvest")}</summary><form className="cm-form" onSubmit={save}>{error && <p role="alert">{messageText(error)}</p>}<PlantingFields api={api} cropId={cycle.crop_id} value={value} onChange={setValue} plantingDate={cycle.planted_on || cycle.plan?.anchor_date} onHarvestSuggestion={setHarvest} /><label>{t("Expected harvest")}<input type="date" value={harvest} onChange={(e) => setHarvest(e.target.value)} /></label><button disabled={busy}>{t("Save planting details")}</button></form></details>;
}

export function InputDraft({ api, initial, onSave, onCancel }) {
  useTranslation();
  const [product, setProduct] = useState(null);
  const [custom, setCustom] = useState(false);
  const [customData, setCustomData] = useState({ input_type: "other", product_name: "", brand_name: "", manufacturer_name: "", active_ingredient: "", formulation: "" });
  const [facts, setFacts] = useState(initial || { quantity: "", unit: "kg", application_method: "", target_reason: "", notes: "" });
  const [error, setError] = useState("");
  function field(e) { setFacts({ ...facts, [e.target.name]: e.target.value }); }
  function save() {
    if (!Number.isFinite(Number(facts.quantity)) || Number(facts.quantity) <= 0 || (!initial && !product && !custom) || (custom && !customData.product_name.trim())) { setError("Choose an input (or enter its name) and a positive quantity."); return; }
    const data = { quantity: facts.quantity, unit: facts.unit, application_method: facts.application_method || null, target_reason: facts.target_reason || null, notes: facts.notes || null };
    onSave(initial ? data : { ...data, farm_input_product_id: custom ? null : product.farm_input_product_id, custom_product: custom ? customData : null }, custom ? customData : product);
  }
  return <section className="cm-card"><h3>{initial ? t("Correct actual input quantity/details") : t("Add actual input")}</h3><p>{t("Record what was used. This is not a dosage recommendation.")}</p>{error && <p role="alert">{messageText(error)}</p>}
    {!initial && <><label>{t("Product not listed?")}<input type="checkbox" checked={custom} onChange={(e) => setCustom(e.target.checked)} /></label>
      {!custom && product && <p>{[product.brand_name, product.manufacturer_name, product.active_ingredient, product.formulation].filter(Boolean).join(" · ")}</p>}
      {custom ? <><label>{t("Input type")}<select value={customData.input_type} onChange={(e) => setCustomData({ ...customData, input_type: e.target.value })}>{types.map((t) => <option key={t} value={t}>{label(t)}</option>)}</select></label>{["product_name", "brand_name", "manufacturer_name", "active_ingredient", "formulation"].map((k) => <label key={k}>{label(k)}{k === "product_name" ? t(" (required)") : t(" (optional)")}<input maxLength={200} value={customData[k]} onChange={(e) => setCustomData({ ...customData, [k]: e.target.value })} /></label>)}<p>{t("This unlisted product stays in your activity history. It does not create a verified catalogue entry.")}</p></> : <><p>{t("Selected: ")}{product?.product_name || t("None")}</p><CatalogueSearch api={api} path="/catalogue/farm-input-products" title={t("product / brand / manufacturer / ingredient")} idKey="farm_input_product_id" nameKey="product_name" onSelect={(p) => { setProduct(p); setFacts({ ...facts, unit: p.default_unit || facts.unit }); }} /></>}
    </>}
    <div className="cm-form"><label>{t("Quantity")}<input type="number" name="quantity" min="0.0001" step="0.0001" value={facts.quantity} onChange={field} /></label><label>{t("Unit")}<select name="unit" value={facts.unit} onChange={field}>{units.map((u) => <option key={u} value={u}>{u}</option>)}</select></label><details><summary>{t("Application details and notes (optional)")}</summary>{["application_method", "target_reason", "notes"].map((k) => <label key={k}>{label(k)}{t(" (optional)")}<input name={k} value={facts[k] || ""} onChange={field} maxLength={k === "application_method" ? 200 : undefined} /></label>)}</details></div>
    <div className="cm-row"><button type="button" onClick={onCancel}>{t("Cancel input")}</button><button type="button" onClick={save}>{initial ? t("Save correction") : t("Add input")}</button></div>
  </section>;
}

export function InputHistory({ api, activity, officer = false, canEdit = true }) {
  useTranslation();
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [adding, setAdding] = useState(false);
  const [requestKey, setRequestKey] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const path = `${officer ? "/field-work/activities" : "/my/farm-activities"}/${activity.activity_id}/inputs`;
  useEffect(() => {
    if (!open) return;
    let active = true;
    api(`${path}?limit=50&offset=${offset}`).then((data) => { if (active) { setItems(data); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, open, path, offset, revision]);
  async function save(data) {
    if (busy) return; setBusy(true); setError("");
    try { await api(edit ? `${path}/${edit.farm_activity_input_id}` : path, edit ? "PUT" : "POST", edit ? { ...data, expected_updated_at: edit.updated_at } : { ...data, request_key: requestKey }); setAdding(false); setEdit(null); setRevision((n) => n + 1); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section><button type="button" onClick={() => setOpen(!open)}>{open ? t("Hide") : t("View / add")}{t(" actual inputs")}</button>{open && <>
    {error && <p role="alert">{messageText(error)} <button type="button" onClick={() => setRevision((n) => n + 1)}>{t("Refresh")}</button></p>}
    {canEdit && <button type="button" disabled={busy} onClick={() => { setAdding(true); setEdit(null); setRequestKey(crypto.randomUUID()); }}>{t("+ Add Input")}</button>}
    {(adding || edit) && canEdit && <fieldset disabled={busy}><InputDraft key={edit?.farm_activity_input_id || requestKey} api={api} initial={edit} onCancel={() => { setAdding(false); setEdit(null); }} onSave={save} /></fieldset>}
    {items === null ? <p>{t("Loading inputs…")}</p> : !items.length ? <p>{t("No inputs recorded on this page.")}</p> : items.map((i) => <article className="cm-card" key={i.farm_activity_input_id}><h3>{i.product_snapshot.product_name}{i.is_unlisted ? t(" (unlisted)") : ""}</h3><p>{i.quantity} {i.unit} · {label(i.product_snapshot.input_type)}</p><p>{[i.product_snapshot.brand_name, i.product_snapshot.manufacturer_name, i.product_snapshot.active_ingredient, i.product_snapshot.formulation].filter(Boolean).join(" · ")}</p>{i.product_snapshot.nutrient_composition && <p>{t("Labelled nutrients: ")}{Object.entries(i.product_snapshot.nutrient_composition).map(([k, v]) => `${k} ${v}%`).join(", ")}</p>}{i.application_method && <p>{t("Method: ")}{i.application_method}</p>}{i.target_reason && <p>{t("Reason: ")}{i.target_reason}</p>}{i.notes && <p>{i.notes}</p>}{canEdit && <button type="button" disabled={busy} onClick={() => { setEdit(i); setAdding(false); }}>{t("Correct quantity / notes")}</button>}</article>)}
    <div className="cm-row"><button type="button" disabled={!offset} onClick={() => setOffset(offset - 50)}>{t("Previous inputs")}</button><button type="button" disabled={!items || items.length < 50} onClick={() => setOffset(offset + 50)}>{t("Next inputs")}</button></div>
  </>}</section>;
}
