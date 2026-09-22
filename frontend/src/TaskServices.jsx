import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useState } from "react";
import BookingForm from "./BookingForm";
import { displayDate, label } from "./cropApi";

export function TaskServiceBooking({ api, token, task, onDone, onCancel, onMarketplace }) {
  useTranslation();
  const [context, setContext] = useState(null);
  const [services, setServices] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const c = await api(`/my/crop-tasks/${task.crop_task_id}/service-context`);
        if (!c.can_book) throw new Error("This task is no longer available for a new booking.");
        const list = await api(`/services?category_id=${c.service_category_id}`);
        if (active) { setContext(c); setServices(list.filter((s) => s.base_price != null)); setError(""); }
      } catch (err) { if (active) setError(err.message); }
    }
    load(); return () => { active = false; };
  }, [api, task.crop_task_id, attempt]);
  return <section className="cm-card"><h2>{t("Book Service: ")}{task.title}</h2><p>{t("Due ")}{displayDate(task.due_date)} · {task.service_category_name_snapshot}</p>
    <div className="cm-row"><button onClick={onCancel}>{t("Back to Crop Task")}</button><button onClick={onMarketplace}>{t("Browse Marketplace")}</button></div>
    {error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Retry")}</button></p>}
    {!services && !error && <p>{t("Loading services…")}</p>}
    {services?.length === 0 && <p>{t("No matching services are currently available. You can return to the task and Record Work yourself.")}</p>}
    {!selected && services?.map((s) => <article className="cm-card" key={s.supplier_service_id}><h3>{s.service_name}</h3><p>{s.supplier_name} · ₹{s.base_price} / {s.pricing_unit}</p><p>{s.description}</p><button onClick={() => setSelected(s)}>{t("Choose Service & Time")}</button></article>)}
    {selected && context && <BookingForm key={selected.supplier_service_id} service={selected} token={token} cropContext={context} onClose={() => setSelected(null)} onBookingCreated={onDone} />}
  </section>;
}

export function TaskServiceActions({ api, task, cycle, revision, onBook, onView, onConfirm, onExpense, onComplete, busy }) {
  useTranslation();
  const [bookings, setBookings] = useState([]);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!task.service_category_id) return;
    let active = true;
    api(`/my/crop-tasks/${task.crop_task_id}/bookings`).then((data) => { if (active) { setBookings(data); setError(""); } }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, task.crop_task_id, task.service_category_id, revision, attempt]);
  if (!task.service_category_id) return null;
  const actionable = ["pending", "in_progress", "partial"].includes(task.status);
  const current = ["planned", "active"].includes(cycle.status);
  const hasOpenBooking = bookings.some((b) => ["pending", "quoted", "confirmed", "in_progress"].includes(b.status));
  return <section className="cm-card"><p>{t("Service category: ")}{task.service_category_name_snapshot}</p>
    {current && actionable && <button disabled={busy} onClick={onBook}>{hasOpenBooking ? t("Book Another Service") : t("Book Service")}</button>}
    {hasOpenBooking && <p>{t("A service is already booked. Only book another if additional work is needed.")}</p>}
    {bookings.length > 0 && <button onClick={() => setAttempt((n) => n + 1)}>{t("Refresh service status")}</button>}
    {error && <p role="alert">{messageText(error)} <button onClick={() => setAttempt((n) => n + 1)}>{t("Refresh bookings")}</button></p>}
    {bookings.map((b) => <div className="cm-card" key={b.booking_id}><p><strong>{b.status === "completed" ? t("Service completed") : b.status === "pending" ? t("Service booked") : b.status === "in_progress" ? t("Work in progress") : label(b.status)}</strong></p><p>{b.supplier_name} · {displayDate(b.requested_start_at?.slice(0, 10))} · {b.requested_start_at?.slice(11, 16)}</p>
      <div className="cm-row"><button onClick={() => onView(b.booking_id)}>{t("View Booking")}</button>
        {current && b.status === "completed" && !b.activity_id && <button disabled={busy} onClick={() => onConfirm(b)}>{t("Confirm Work")}</button>}
        {b.activity_id && <><span>{t("Work recorded")}</span>{current && Number(b.expense_count) === 0 && <button disabled={busy} onClick={() => onExpense(b)}>{t("Record Expense")}</button>}{Number(b.expense_count) > 0 && <span>{t("Expense recorded")}</span>}
          {(cycle.status === "active" || (cycle.status === "planned" && !!task.phase)) && actionable && <button disabled={busy} onClick={onComplete}>{t("Complete Task")}</button>}</>}
      </div></div>)}
  </section>;
}

export function BookingCropOrigin({ booking, onOpenCrop }) {
  useTranslation();
  const c = booking.crop_context_snapshot;
  if (!c) return null;
  return <div><p>{t("Crop: ")}{c.crop_name}{c.season ? ` · ${c.season}` : ""} · {c.title}</p><p>{[c.farm_name, c.plot_name, c.block_name].filter(Boolean).join(" · ")}</p>{onOpenCrop && <button onClick={() => onOpenCrop(c.farm_crop_id)}>{t("Open Crop Task")}</button>}</div>;
}
