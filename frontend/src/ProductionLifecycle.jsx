import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useState } from "react";
import { displayDate, seasonLabel } from "./cropApi";
import { cropStatusLabel } from "./farmerLabels";
import { HarvestSummary } from "./CropHarvests";

export function ReconciliationSummary({ data }) {
  useTranslation();
  return <><HarvestSummary summary={data} />{data.quantities.map((q) => <p key={q.unit}><strong>{t("Remaining: ")}{Number(q.remaining_quantity).toLocaleString("en-IN", { maximumFractionDigits: 4 })} {q.unit}</strong></p>)}
    <p>{t("Remaining produce can stay unsold. Totals include later corrections to harvests, sales and expenses.")}</p>
    {data.completed_at && <p>{t("Completed ")}{displayDate(data.completed_at.slice(0, 10))}{data.completion_note ? ` · ${data.completion_note}` : ""}</p>}</>;
}

export function CompletionReview({ api, cycle, onChanged }) {
  useTranslation();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [done, setDone] = useState(false);
  const active = cycle.status === "active";
  const needsSeasons = cycle.lifecycle_type === "perennial" && !cycle.perennial_planting_id;
  const title = cycle.perennial_planting_id ? "Close Season" : "Complete Crop";
  async function review() {
    setBusy(true); setError("");
    try { setData(await api(`/my/crop-cycles/${cycle.farm_crop_id}/reconciliation`)); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function complete(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    try { const result = await api(`/my/crop-cycles/${cycle.farm_crop_id}/complete`, "POST", { note: note.trim() || null }); setData(result); setDone(true); await onChanged(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="cm-card"><h2>{active ? title : t("Crop totals")}</h2>
    {needsSeasons && active && <p>{t("Enable seasons below before closing this season. Your planting will remain available for next year.")}</p>}
    <button disabled={busy} onClick={review}>{data ? t("Update totals") : active && !needsSeasons ? title : t("View crop totals")}</button>
    {error && <p className="cm-error" role="alert">{messageText(error)}</p>}{data && <ReconciliationSummary data={data} />}
    {data && active && !needsSeasons && !done && <form className="cm-form" onSubmit={complete}><p>{t("Unfinished plan tasks will be cancelled with an explanation. All work, inputs, harvests, sales and costs remain available in History.")}{cycle.perennial_planting_id ? t(" The planting stays available for a future season.") : ""}</p>
      <label>{t("Completion note (optional)")}<textarea maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} /></label><div className="cm-row"><button className="primary-button" disabled={busy}>{t("Confirm Completion")}</button><button type="button" disabled={busy} onClick={() => setData(null)}>{t("Keep Open")}</button></div></form>}
    {done && <p role="status">{cycle.perennial_planting_id ? t("Season closed. Your planting remains available.") : t("Crop completed.")}{t(" Saved records are available in History.")}</p>}
  </section>;
}

function SeasonForm({ api, cycle, planting, onSaved, onCancel }) {
  useTranslation();
  const [name, setName] = useState("");
  const [started, setStarted] = useState(planting?.next_season?.period_started_on || cycle.period_started_on || "");
  const [harvest, setHarvest] = useState("");
  const [key] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    try {
      const saved = await api(planting ? `/my/perennial-plantings/${planting.perennial_planting_id}/seasons` : `/my/crop-cycles/${cycle.farm_crop_id}/enable-seasons`, "POST", { season: name || null, period_started_on: started, ...(planting ? { expected_harvest_on: harvest || null, request_key: key } : {}) });
      await onSaved(saved);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <form className="cm-form" onSubmit={save}><h3>{planting ? t("Start Next Season") : t("Enable Seasons")}</h3>
    <p>{planting ? t("A fresh season will use this same planting. Previous work, plans and costs stay in their original season.") : t("This crop becomes the first season of a continuing planting. Its existing records stay together.")}</p>
    <p>{t("Season: ")}{name || seasonLabel(started, "perennial") || t("Choose season start")}</p>
    <details><summary>{t("Correct season label (optional)")}</summary><label>{t("Custom label")}<input maxLength={50} value={name} onChange={(e) => setName(e.target.value)} /></label></details>
    <label>{t("Season start date")}<input required type="date" min={cycle.planted_on || undefined} value={started} onChange={(e) => setStarted(e.target.value)} /></label>
    {planting && <label>{t("Expected harvest (optional)")}<input type="date" min={started || undefined} value={harvest} onChange={(e) => setHarvest(e.target.value)} /></label>}
    <p className="cm-note">{t("Actual planting date remains ")}{displayDate(cycle.planted_on)}{t(". Season start is a separate date.")}</p>
    {error && <p className="cm-error" role="alert">{messageText(error)}</p>}<div className="cm-row"><button disabled={busy}>{planting ? t("Start Season") : t("Enable Seasons")}</button><button type="button" disabled={busy} onClick={onCancel}>{t("Cancel")}</button></div></form>;
}

export function SeasonPanel({ api, cycle, onChanged, onOpen }) {
  useTranslation();
  const [planting, setPlanting] = useState(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!cycle.perennial_planting_id) return;
    let active = true;
    api(`/my/perennial-plantings/${cycle.perennial_planting_id}`).then((p) => { if (active) { setPlanting(p); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, cycle.perennial_planting_id, cycle.status, attempt]);
  if (!cycle.perennial_planting_id && !(cycle.lifecycle_type === "perennial" && ["active", "harvested"].includes(cycle.status) && cycle.planted_on)) return null;
  const open = planting?.seasons.some((s) => ["active", "planned"].includes(s.status));
  return <section className="cm-card"><h2>{t("Planting & seasons")}</h2><p>{cycle.perennial_planting_id ? t("Your planting continues across seasons. Each season keeps its own work, costs and harvests.") : t("Keep this perennial planting available for future seasons.")}</p>
    {error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}
    {cycle.perennial_planting_id && !planting && !error && <p>{t("Loading seasons…")}</p>}
    {planting?.seasons.map((s) => <div className="cm-row" key={s.farm_crop_id}><p>{s.season} · {displayDate(s.period_started_on)} · {cropStatusLabel({ ...s, perennial_planting_id: cycle.perennial_planting_id })}</p><button disabled={s.farm_crop_id === cycle.farm_crop_id} onClick={() => onOpen(s.farm_crop_id)}>{t("Open Season")}</button></div>)}
    {!adding && (!cycle.perennial_planting_id || (planting && !open)) && <button onClick={() => setAdding(true)}>{planting ? t("+ Start Next Season") : t("Enable Seasons")}</button>}
    {open && <p>{t("Close the current season before starting the next one.")}</p>}
    {adding && <SeasonForm api={api} cycle={cycle} planting={planting} onCancel={() => setAdding(false)} onSaved={async (saved) => { setAdding(false); await onChanged(); setAttempt((n) => n + 1); if (saved.farm_crop_id) onOpen(saved.farm_crop_id); }} />}
  </section>;
}

export function PerennialPlantings({ api, onOpen }) {
  useTranslation();
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api(`/my/perennial-plantings?limit=20&offset=${offset}`).then((p) => { if (active) { setItems(p); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, offset, attempt]);
  if (items?.length === 0 && !offset && !error) return null;
  return <section className="cm-card"><h2>{t("Perennial plantings")}</h2>{error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}{!items && !error && <p>{t("Loading plantings…")}</p>}
    {items?.map((p) => <article key={p.perennial_planting_id}><h3>{p.crop_name}</h3><p>{[p.farm_name, p.plot_name, p.block_name].filter(Boolean).join(" · ")}</p><button onClick={() => onOpen(p.source_farm_crop_id)}>{t("View Seasons / Start Next Season")}</button></article>)}
    <div className="cm-row"><button disabled={!offset || !items} onClick={() => { setItems(null); setOffset((n) => n - 20); }}>{t("Previous plantings")}</button><button disabled={!items || items.length < 20} onClick={() => { setItems(null); setOffset((n) => n + 20); }}>{t("Next plantings")}</button></div></section>;
}
