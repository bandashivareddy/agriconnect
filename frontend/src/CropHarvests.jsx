import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useCallback, useEffect, useState } from "react";
import { displayDate } from "./cropApi";
import { saleTotal, revealInvalidField } from "./farmerUx";

const units = ["kg", "g", "tonne", "quintal", "unit", "crate", "box", "bag", "bunch"];
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const money = (value) => Number(value).toLocaleString("en-IN", { style: "currency", currency: "INR" });
const quantity = (value) => Number(value).toLocaleString("en-IN", { maximumFractionDigits: 4 });

async function harvestContext(api, base, eventId) {
  const harvest = await api(`${base}/${eventId}`);
  let sales = [], page;
  do {
    page = await api(`${base}/${eventId}/sales?limit=100&offset=${sales.length}`);
    sales = sales.concat(page);
  } while (page.length === 100);
  const sold = sales.reduce((sum, sale) => sum + Number(sale.quantity_sold), 0);
  return { ...harvest, quantity_sold: sold,
    available_quantity: Math.max(0, Number((Number(harvest.quantity) - Number(harvest.wastage_quantity || 0) - sold).toFixed(4))),
    total_revenue: sales.reduce((sum, sale) => sum + Number(sale.total_amount), 0) };
}

export function HarvestSummary({ summary, financialOnly = false }) {
  useTranslation();
  return <>{!financialOnly && summary.quantities.length ? summary.quantities.map((q) => <p key={q.unit}><strong>{t("Harvested: ")}{quantity(q.total_harvested_quantity)} {q.unit}</strong>{t(" · Wastage: ")}{quantity(q.total_wastage)} {q.unit}{t(" · Sold: ")}{quantity(q.total_sold_quantity)} {q.unit}</p>) : <p>{t("No harvests recorded yet.")}</p>}
    <dl className="cm-summary"><div><dt>{t("Expenses")}</dt><dd>{money(summary.total_expenses)}</dd></div><div><dt>{t("Revenue")}</dt><dd>{money(summary.total_revenue)}</dd></div><div><dt>{t("Net return")}</dt><dd>{money(summary.net_return)}</dd></div></dl>
    <p className="cm-note">{t("Net return is recorded sales minus expenses linked to this crop.")}</p></>;
}

export function HarvestForm({ api, base, initial, onSaved, onCancel }) {
  useTranslation();
  const [form, setForm] = useState(initial || { harvested_on: today(), quantity: "", unit: "kg", grade: "", wastage_quantity: "", notes: "" });
  const [key] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function field(e) { setForm((old) => ({ ...old, [e.target.name]: e.target.value })); }
  async function save(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    const data = { harvested_on: form.harvested_on, quantity: form.quantity, unit: form.unit, grade: form.grade || null, wastage_quantity: form.wastage_quantity === "" || form.wastage_quantity == null ? null : form.wastage_quantity, notes: form.notes || null };
    try { const saved = await api(initial ? `${base}/${initial.harvest_event_id}` : base, initial ? "PUT" : "POST", { ...data, ...(initial ? { expected_updated_at: initial.updated_at } : { request_key: key }) }); onSaved(saved); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <form onInvalid={revealInvalidField} className="cm-card cm-form" onSubmit={save}><h3>{initial ? t("Correct Harvest") : t("Record Harvest")}</h3><p>{t("Saving this harvest keeps the crop status unchanged.")}</p>
    <label>{t("Date")}<input type="date" name="harvested_on" required value={form.harvested_on} onChange={field} /></label>
    <label>{t("Quantity")}<input type="number" inputMode="decimal" name="quantity" min="0.0001" step="0.0001" required value={form.quantity} onChange={field} /></label>
    <label>{t("Unit")}<select name="unit" value={form.unit} onChange={field}>{units.map((u) => <option key={u} value={u}>{u}</option>)}</select></label>
    <details><summary>{t("Grade, wastage and notes (optional)")}</summary><label>{t("Grade / quality (optional)")}<input name="grade" maxLength={100} value={form.grade || ""} onChange={field} /></label>
    <label>{t("Wastage (")}{form.unit}{t(", optional)")}<input type="number" inputMode="decimal" name="wastage_quantity" min="0" max={form.quantity || undefined} step="0.0001" value={form.wastage_quantity ?? ""} onChange={field} /></label>
    <label>{t("Notes (optional)")}<textarea name="notes" value={form.notes || ""} onChange={field} /></label></details>
    {error && <p className="cm-error" role="alert">{messageText(error)}</p>}<div className="cm-row"><button className="primary-button" disabled={busy}>{t("Save Harvest")}</button><button type="button" disabled={busy} onClick={onCancel}>{t("Cancel")}</button></div></form>;
}

export function SaleForm({ api, base, harvest, initial, onSaved, onCancel }) {
  useTranslation();
  const [form, setForm] = useState(initial || { sold_on: today(), quantity_sold: "", price_per_unit: "", total_amount: "", buyer_name: "", notes: "" });
  const [remaining, setRemaining] = useState(Number(harvest.available_quantity));
  const available = Number((remaining + Number(initial?.quantity_sold || 0)).toFixed(4));
  const calculated = form.price_per_unit !== "" && form.price_per_unit != null;
  const total = calculated ? saleTotal(form.quantity_sold, form.price_per_unit) : "";
  const [key] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function field(e) { setForm((old) => ({ ...old, [e.target.name]: e.target.value })); }
  async function save(e) {
    e.preventDefault(); if (busy) return; if (Number(form.quantity_sold) > available) { setError({ key: "Only {{v0}} {{v1}} is available for this sale. Reduce the quantity or check the harvest record.", values: { v0: quantity(available), v1: harvest.unit } }); return; } setBusy(true); setError("");
    const data = { sold_on: form.sold_on, quantity_sold: form.quantity_sold, unit: harvest.unit, price_per_unit: form.price_per_unit || null, total_amount: calculated ? null : form.total_amount || null, buyer_name: form.buyer_name || null, notes: form.notes || null };
    const path = `${base}/${harvest.harvest_event_id}/sales`;
    try { const saved = await api(initial ? `${path}/${initial.harvest_sale_id}` : path, initial ? "PUT" : "POST", { ...data, ...(initial ? { expected_updated_at: initial.updated_at } : { request_key: key }) }); onSaved(saved); }
    catch (err) {
      setError(err.message);
      try {
        const latest = await harvestContext(api, base, harvest.harvest_event_id);
        setRemaining(latest.available_quantity);
        const nowAvailable = Number((latest.available_quantity + Number(initial?.quantity_sold || 0)).toFixed(4));
        setError(Number(form.quantity_sold) > nowAvailable
          ? `Only ${quantity(nowAvailable)} ${harvest.unit} is available now. Reduce the sale quantity or check the harvest record.`
          : `${err.message} Available now: ${quantity(nowAvailable)} ${harvest.unit}.`);
      } catch { /* Keep the original save error if refreshing is unavailable. */ }
    } finally { setBusy(false); }
  }
  return <form onInvalid={revealInvalidField} className="cm-card cm-form" onSubmit={save}><h3>{initial ? t("Correct Sale") : t("Record Sale")}</h3><p>{t("Harvest: ")}{displayDate(harvest.harvested_on)}{t(" · Available: ")}{quantity(available)} {harvest.unit}</p>
    <label>{t("Sale date")}<input type="date" name="sold_on" min={harvest.harvested_on} required value={form.sold_on} onChange={field} /></label>
    <label>{t("Quantity sold (")}{harvest.unit})<input type="number" inputMode="decimal" name="quantity_sold" min="0.0001" step="0.0001" required value={form.quantity_sold} onChange={field} /></label>
    <label>{t("Price per ")}{harvest.unit}{t(" (₹, optional)")}<input type="number" inputMode="decimal" name="price_per_unit" min="0.0001" step="0.0001" value={form.price_per_unit ?? ""} onChange={field} /></label>
    <label>{t("Total amount (₹)")}<input type="number" inputMode="decimal" name="total_amount" min="0.01" step="0.01" readOnly={calculated} required={!calculated} value={calculated ? total : form.total_amount ?? ""} onChange={field} /></label><p className="cm-note">{t("With a price per unit, the total is calculated automatically and confirmed when saved. For a lump-sum sale, leave price blank and enter the total.")}</p>
    <details><summary>{t("Buyer and notes (optional)")}</summary><label>{t("Buyer (optional)")}<input name="buyer_name" maxLength={200} value={form.buyer_name || ""} onChange={field} /></label>
    <label>{t("Notes (optional)")}<textarea name="notes" value={form.notes || ""} onChange={field} /></label></details>
    {error && <p className="cm-error" role="alert">{messageText(error)}</p>}<div className="cm-row"><button className="primary-button" disabled={busy}>{t("Save Sale")}</button><button type="button" disabled={busy} onClick={onCancel}>{t("Cancel")}</button></div></form>;
}

function HarvestCard({ api, base, harvest, allowEdits, onEdit, onSale, initiallyOpen = false }) {
  useTranslation();
  const [open, setOpen] = useState(initiallyOpen);
  const [sales, setSales] = useState(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    api(`${base}/${harvest.harvest_event_id}/sales?limit=20&offset=${offset}`).then((data) => { if (active) { setSales(data); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, base, harvest.harvest_event_id, open, offset, attempt]);
  return <article className="cm-card"><h3>{displayDate(harvest.harvested_on)} · {quantity(harvest.quantity)} {harvest.unit}</h3>
    {harvest.grade && <p>{t("Grade: ")}{harvest.grade}</p>}<p>{t("Wastage: ")}{quantity(harvest.wastage_quantity || 0)} {harvest.unit}{t(" · Sold: ")}{quantity(harvest.quantity_sold)} {harvest.unit}{t(" · Available: ")}{quantity(harvest.available_quantity)} {harvest.unit}</p><p>{t("Revenue: ")}{money(harvest.total_revenue)}</p>{harvest.notes && <p>{harvest.notes}</p>}
    <div className="cm-row">{allowEdits && <><button disabled={Number(harvest.available_quantity) <= 0} onClick={() => onSale(harvest)}>{t("Record Sale")}</button><button onClick={() => onEdit(harvest)}>{t("Correct Harvest")}</button></>}<button aria-expanded={open} onClick={() => setOpen((v) => !v)}>{open ? t("Hide Sales") : t("View Sales")}</button></div>
    {open && <>{error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}{!sales && !error && <p>{t("Loading sales…")}</p>}{sales && sales.length ? sales.map((sale) => <section className="cm-card" key={sale.harvest_sale_id}><p>{displayDate(sale.sold_on)} · {quantity(sale.quantity_sold)} {sale.unit} · {money(sale.total_amount)}</p>{sale.buyer_name && <p>{t("Buyer: ")}{sale.buyer_name}</p>}{sale.notes && <p>{sale.notes}</p>}{allowEdits && <button onClick={() => onSale(harvest, sale)}>{t("Correct Sale")}</button>}</section>) : <p>{t("No sales recorded.")}</p>}
      <div className="cm-row"><button disabled={!offset} onClick={() => { setSales(null); setOffset((n) => n - 20); }}>{t("Previous sales")}</button><span>{t("Page ")}{offset / 20 + 1}</span><button disabled={!sales || sales.length < 20} onClick={() => { setSales(null); setOffset((n) => n + 20); }}>{t("Next sales")}</button></div></>}
  </article>;
}

export default function CropHarvests({ api, cycleId, history = false }) {
  useTranslation();
  const base = `/my/crop-cycles/${cycleId}/harvests`;
  const [records, setRecords] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [form, setForm] = useState(null);
  const [focused, setFocused] = useState(null);
  const [focusLoading, setFocusLoading] = useState(false);
  const [manageHistory, setManageHistory] = useState(false);
  const allowEdits = !history || manageHistory;
  const reload = useCallback(() => { setRecords(null); setSummary(null); setRevision((n) => n + 1); }, []);
  useEffect(() => {
    let active = true;
    Promise.all([api(`${base}?limit=20&offset=${offset}`), api(`/my/crop-cycles/${cycleId}/harvest-summary`)]).then(([items, totals]) => { if (active) { setRecords(items); setSummary(totals); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, base, cycleId, offset, revision]);
  async function saved(record) {
    const eventId = record.harvest_event_id;
    setForm(null); setFocused(null); setFocusLoading(true); reload();
    try {
      const harvest = await harvestContext(api, base, eventId);
      setFocused({ ...harvest, savedSale: record.harvest_sale_id ? record : null });
    } catch (err) { setError({ key: "Saved successfully. Could not open the saved harvest: {{v0}}", values: { v0: err.message } }); }
    finally { setFocusLoading(false); }
  }
  useEffect(() => { if (focused && !form) document.getElementById("saved-harvest")?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [focused, form]);
  return <><section className="cm-card"><h2>{t("Harvests")}</h2>{summary && <HarvestSummary summary={summary} />}{history && <p>{t("Saved harvests and sales remain available. You can correct records or add a late entry.")}</p>}
    <div className="cm-row">{history && !manageHistory && <button onClick={() => setManageHistory(true)}>{t("Correct / add historical records")}</button>}{allowEdits && <button disabled={!!form} className="primary-button" onClick={() => setForm({ type: "harvest" })}>{t("+ Record Harvest")}</button>}<button disabled={!!form} onClick={reload}>{t("Refresh")}</button></div></section>
    {error && <p className="cm-error" role="alert">{messageText(error)} <button onClick={reload}>{t("Retry")}</button></p>}
    {form?.type === "harvest" && <HarvestForm key={form.initial?.harvest_event_id || "new"} api={api} base={base} initial={form.initial} onSaved={saved} onCancel={() => setForm(null)} />}
    {form?.type === "sale" && <SaleForm key={form.initial?.harvest_sale_id || `new-${form.harvest.harvest_event_id}`} api={api} base={base} harvest={form.harvest} initial={form.initial} onSaved={saved} onCancel={() => setForm(null)} />}
    {focusLoading && <p role="status">{t("Opening saved harvest...")}</p>}
    {focused && !form && <section id="saved-harvest" className="cm-saved"><p role="status">{t("Saved successfully")}</p>{focused.savedSale && <p>{t("Saved sale: ")}{quantity(focused.savedSale.quantity_sold)} {focused.unit} / {money(focused.savedSale.total_amount)}</p>}<HarvestCard key={`focused-${revision}`} api={api} base={base} harvest={focused} initiallyOpen={!!focused.savedSale} allowEdits={allowEdits} onEdit={(initial) => setForm({ type: "harvest", initial })} onSale={(harvest, initial) => setForm({ type: "sale", harvest, initial })} /><button onClick={() => setFocused(null)}>{t("Back to harvests")}</button></section>}
    {!records && !error && <p>{t("Loading harvests…")}</p>}{records?.map((h) => <HarvestCard key={`${revision}-${h.harvest_event_id}`} api={api} base={base} harvest={h} allowEdits={allowEdits && !form} onEdit={(initial) => setForm({ type: "harvest", initial })} onSale={(harvest, initial) => setForm({ type: "sale", harvest, initial })} />)}
    <nav className="cm-row" aria-label={t("Harvest pages")}><button disabled={!offset || !records || !!form} onClick={() => { setRecords(null); setOffset((n) => n - 20); }}>{t("Previous")}</button><span>{t("Page ")}{offset / 20 + 1}</span><button disabled={!records || records.length < 20 || !!form} onClick={() => { setRecords(null); setOffset((n) => n + 20); }}>{t("Next")}</button></nav></>;
}
