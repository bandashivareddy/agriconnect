import { useEffect, useState } from "react";
import "./SupplierAvailability.css";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function SupplierAvailability({ token, onBack }) {
  const [services, setServices] = useState([]);
  const [equipment, setEquipment] = useState([]);
  const [slots, setSlots] = useState([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [showAddAvailability, setShowAddAvailability] = useState(false);
  const [form, setForm] = useState({ itemType: "service", itemId: "", date: "", hours: [], capacity: "1" });
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  async function refreshSlots() {
    const response = await fetch(`${API_URL}/supplier/availability`, { headers });
    const data = await response.json();
    if (!response.ok || !Array.isArray(data)) throw new Error("Could not load availability slots.");
    setSlots(data);
  }

  useEffect(() => {
    async function loadAvailabilityData() {
      try {
        const [servicesResponse, equipmentResponse, slotsResponse] = await Promise.all([
          fetch(`${API_URL}/supplier/services`, { headers }),
          fetch(`${API_URL}/supplier/equipment`, { headers }),
          fetch(`${API_URL}/supplier/availability`, { headers }),
        ]);
        const [serviceData, equipmentData, slotData] = await Promise.all([servicesResponse.json(), equipmentResponse.json(), slotsResponse.json()]);
        if (!servicesResponse.ok || !Array.isArray(serviceData)) throw new Error("Could not load supplier services.");
        if (!equipmentResponse.ok || !Array.isArray(equipmentData)) throw new Error("Could not load supplier equipment.");
        if (!slotsResponse.ok || !Array.isArray(slotData)) throw new Error("Could not load availability slots.");
        setServices(serviceData); setEquipment(equipmentData); setSlots(slotData);
        setForm((current) => ({ ...current, itemId: String(serviceData[0]?.supplier_service_id || equipmentData[0]?.equipment_id || "") }));
      } catch (error) { console.error(error); setMessage(error.message || "Could not load availability data."); }
    }
    loadAvailabilityData();
  }, [token]);

  function updateField({ target: { name, value } }) {
    if (name === "itemType") {
      const nextItems = value === "service" ? services : equipment;
      setForm((current) => ({ ...current, itemType: value, itemId: String(value === "service" ? nextItems[0]?.supplier_service_id || "" : nextItems[0]?.equipment_id || ""), hours: [] }));
    } else if (name === "date") {
      setForm((current) => ({ ...current, date: value, hours: [] })); setMessage("");
    } else setForm((current) => ({ ...current, [name]: value }));
  }

  function getTodayString() {
    const date = new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }
  function isHourInPast(hour) {
    if (!form.date) return false;
    const now = new Date(); const date = new Date(`${form.date}T00:00:00`);
    const today = date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
    return today && new Date(date.getFullYear(), date.getMonth(), date.getDate(), hour) <= now;
  }
  function toggleHour(hour) {
    if (isHourInPast(hour)) return;
    setForm((current) => ({ ...current, hours: current.hours.includes(hour) ? current.hours.filter((item) => item !== hour) : [...current.hours, hour].sort((a, b) => a - b) }));
  }
  function selectAllHours() { setForm((current) => ({ ...current, hours: Array.from({ length: 24 }, (_, hour) => hour).filter((hour) => !isHourInPast(hour)) })); }
  function clearAllHours() { setForm((current) => ({ ...current, hours: [] })); }
  function formatHour(hour) { if (hour === 0) return "12 AM"; if (hour === 12) return "12 PM"; return hour < 12 ? `${hour} AM` : `${hour - 12} PM`; }
  function formatSlotTime(hour) { return `${formatHour(hour)} – ${formatHour((hour + 1) % 24)}`; }

  async function createSlots(event) {
    event.preventDefault(); setMessage("");
    if (!form.date) return setMessage("Please select a date.");
    if (!form.hours.length) return setMessage("Please select at least one available hour.");
    if (!form.itemId) return setMessage("Please select a service or equipment item.");
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/supplier/availability`, { method: "POST", headers, body: JSON.stringify({
        supplier_service_id: form.itemType === "service" ? Number(form.itemId) : null,
        equipment_id: form.itemType === "equipment" ? Number(form.itemId) : null,
        date: `${form.date}T00:00:00`, hours: form.hours, capacity: Number(form.capacity), status: "available",
      }) });
      const result = await response.json();
      if (!response.ok) return setMessage(result.detail || "Availability slots could not be created.");
      await refreshSlots();
      const count = (result.slots || []).length;
      setMessage(`${count} hourly slot${count === 1 ? "" : "s"} created successfully.`);
      setForm((current) => ({ ...current, hours: [] })); setShowAddAvailability(false);
    } catch (error) { console.error(error); setMessage(error.message || "Availability slots could not be created."); }
    finally { setSaving(false); }
  }

  const selectedItems = form.itemType === "service" ? services : equipment;
  const today = getTodayString();
  const availabilityGroups = slots.filter((slot) => String(slot.starts_at).slice(0, 10) >= today).slice()
    .sort((first, second) => new Date(first.starts_at) - new Date(second.starts_at))
    .reduce((groups, slot) => {
      const previous = groups[groups.length - 1];
      const canJoin = previous && String(previous.starts_at).slice(0, 10) === String(slot.starts_at).slice(0, 10) && previous.item_type === slot.item_type && previous.item_name === slot.item_name && previous.capacity === slot.capacity && previous.status === slot.status && previous.remaining_capacity === slot.remaining_capacity && new Date(previous.ends_at).getTime() === new Date(slot.starts_at).getTime();
      if (canJoin) { previous.ends_at = slot.ends_at; previous.slotIds.push(slot.availability_slot_id); }
      else groups.push({ ...slot, slotIds: [slot.availability_slot_id] });
      return groups;
    }, []);

  return <main className="availability-page"><section className="availability-content">
    <div className="availability-topbar"><button className="availability-back-button" onClick={onBack} aria-label="Back to marketplace">←</button><h1>My Availability</h1><div aria-hidden="true" /></div>
    <p className="availability-intro">Manage when farmers can book your services.</p>
    <section className="availability-list-section">
      {availabilityGroups.length === 0 ? <div className="availability-empty-state"><p>No availability added yet.</p><span>Add available times so farmers can book your services.</span></div> : availabilityGroups.map((slot) => <article className="availability-card" key={slot.slotIds.join("-")}>
        <div><span>{slot.item_type}</span><h3>{slot.item_name}</h3><p>{new Date(slot.starts_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</p><p className="availability-time-range">{new Date(slot.starts_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })} – {new Date(slot.ends_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}</p></div>
        <div className="availability-card-capacity"><strong className={`slot-status slot-${slot.status}`}>{slot.status}</strong><p>Capacity: {slot.capacity}</p>{slot.remaining_capacity !== null && slot.remaining_capacity !== undefined && <p>Available: {slot.remaining_capacity}</p>}</div>
      </article>)}
    </section>
    <section className="availability-add-section">
      <button type="button" className="primary-button availability-add-button" onClick={() => { setMessage(""); setShowAddAvailability((current) => !current); }}>{showAddAvailability ? "Close" : "+ Add Availability"}</button>
      {showAddAvailability && <div className="availability-form-panel"><h2>Add availability</h2><form className="availability-form" onSubmit={createSlots}>
        <label>Listing type<select name="itemType" value={form.itemType} onChange={updateField}><option value="service">Service</option><option value="equipment">Equipment</option></select></label>
        <label>Select listing<select name="itemId" value={form.itemId} onChange={updateField} required><option value="">Select listing</option>{selectedItems.map((item) => <option key={form.itemType === "service" ? item.supplier_service_id : item.equipment_id} value={form.itemType === "service" ? item.supplier_service_id : item.equipment_id}>{form.itemType === "service" ? item.service_name : item.equipment_name}</option>)}</select></label>
        <label>Date<input name="date" type="date" value={form.date} min={today} onChange={updateField} required /></label>
        <label>Capacity per hour<input name="capacity" type="number" min="1" value={form.capacity} onChange={updateField} required /></label>
        <div className="availability-hours"><div className="availability-hours-header"><div><strong>Select available hours</strong><p>Each selected hour represents one 1-hour slot.</p></div><div className="availability-hour-actions"><button type="button" className="secondary-action" onClick={selectAllHours} disabled={!form.date}>Select all</button><button type="button" className="secondary-action" onClick={clearAllHours}>Clear</button></div></div>
          <div className="hour-grid">{Array.from({ length: 24 }, (_, hour) => { const selected = form.hours.includes(hour); const past = isHourInPast(hour); return <button type="button" key={hour} className={`hour-slot ${selected ? "hour-slot-selected" : ""} ${past ? "hour-slot-past" : ""}`} onClick={() => toggleHour(hour)} disabled={past} title={past ? "This time has already passed." : formatSlotTime(hour)}><strong>{formatHour(hour)}</strong><span>{past ? "Past" : selected ? "Available" : "Not selected"}</span></button>; })}</div>
          {form.hours.length > 0 && <div className="selected-hours-summary"><strong>{form.hours.length} hour{form.hours.length === 1 ? "" : "s"} selected</strong><p>{form.hours.slice().sort((a, b) => a - b).map((hour) => formatSlotTime(hour)).join(", ")}</p></div>}
        </div>
        <button type="submit" className="primary-button availability-full-width" disabled={saving || !form.date || form.hours.length === 0}>{saving ? "Saving availability..." : "Save availability"}</button>
      </form></div>}
      {message && <p className="availability-message">{message}</p>}
    </section>
  </section></main>;
}

export default SupplierAvailability;
