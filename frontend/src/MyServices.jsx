import { useEffect, useState } from "react";
import "./MyServices.css";
import { API_BASE_URL, apiError } from "./api";

const API_URL = API_BASE_URL;

function MyServices({ token, onBack, onboarding = false, onComplete }) {
  const [services, setServices] = useState([]);
  const [categories, setCategories] = useState([]);
  const [showAdd, setShowAdd] = useState(onboarding);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({ categoryId: "", description: "", pricingUnit: "acre", basePrice: "", minimumCharge: "", duration: "" });
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  async function load() {
    const [serviceResponse, categoryResponse] = await Promise.all([
      fetch(`${API_URL}/supplier/services`, { headers }), fetch(`${API_URL}/service-categories`),
    ]);
    const [serviceData, categoryData] = await Promise.all([serviceResponse.json(), categoryResponse.json()]);
    if (!serviceResponse.ok || !categoryResponse.ok) throw new Error("Could not load services.");
    setServices(serviceData); setCategories(categoryData);
    if (!categoryData.some((item) => item.parent_category_id != null)) setMessage("No service categories are available. Please contact support to restore the service catalogue.");
    const first = categoryData.find((item) => item.parent_category_id != null);
    setForm((current) => ({ ...current, categoryId: current.categoryId || String(first?.category_id || "") }));
  }
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [token]);
  const children = categories.filter((item) => item.parent_category_id != null);
  const parents = categories.filter((item) => item.parent_category_id == null);
  function update(event) { const { name, value } = event.target; setForm((current) => ({ ...current, [name]: value })); }
  async function add(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true); setMessage("");
    try {
    const response = await fetch(`${API_URL}/supplier/services`, { method: "POST", headers, body: JSON.stringify({ category_id: Number(form.categoryId), description: form.description || null, pricing_unit: form.pricingUnit, base_price: form.pricingUnit === "custom" || !form.basePrice ? null : Number(form.basePrice), minimum_charge: form.minimumCharge ? Number(form.minimumCharge) : null, estimated_duration_minutes: form.duration ? Number(form.duration) : null }) });
    const data = await response.json();
    if (!response.ok) { setMessage(apiError(data, "Service could not be added.")); return; }
    if (onboarding) { onComplete(); return; }
    await load(); setShowAdd(false); setMessage(`${data.service_name} was added successfully.`); setForm((current) => ({ ...current, description: "", basePrice: "", minimumCharge: "", duration: "" }));
    } catch (error) { setMessage(error.message || "Service could not be added. Please try again."); } finally { setSaving(false); }
  }
  function price(service) { return service.base_price == null ? "Custom quote" : `₹${Number(service.base_price).toLocaleString("en-IN")} / ${service.pricing_unit}`; }
  return <main className="my-services-page"><section className="my-services-content"><div className="my-services-topbar"><button aria-label="Back to provider dashboard" onClick={onBack}>←</button><h1>My Services</h1><div /></div><p className="my-services-intro">{onboarding ? "Add at least one service to complete provider setup." : "Manage the agricultural services you offer."}</p><div className="my-services-list">{services.length === 0 ? <p className="my-services-empty">No services added yet. Add your first service so farmers can discover what you offer.</p> : services.map((service) => <article className="my-service-card" key={service.supplier_service_id}><span>{service.parent_category_name || service.category_name || "Agricultural service"}</span><h2>{service.service_name}</h2><p>{price(service)}</p>{service.minimum_charge != null && <p>Minimum charge: ₹{Number(service.minimum_charge).toLocaleString("en-IN")}</p>}{service.estimated_duration_minutes && <p>Duration: {service.estimated_duration_minutes} minutes</p>}<strong>Active</strong></article>)}</div><button className="my-services-add" type="button" onClick={() => setShowAdd((current) => !current)}>{showAdd ? "Close add service" : "+ Add Service"}</button>{showAdd && <form className="my-services-form" onSubmit={add}><label>Service<select name="categoryId" value={form.categoryId} onChange={update} required>{parents.map((parent) => <optgroup key={parent.category_id} label={parent.category_name}>{children.filter((child) => child.parent_category_id === parent.category_id).map((child) => <option key={child.category_id} value={child.category_id}>{child.category_name}</option>)}</optgroup>)}</select></label><label>Pricing unit<select name="pricingUnit" value={form.pricingUnit} onChange={update}>{["acre", "hour", "day", "trip", "fixed", "custom"].map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select></label><label>Base price (₹)<input name="basePrice" type="number" min="0" value={form.basePrice} onChange={update} disabled={form.pricingUnit === "custom"} required={form.pricingUnit !== "custom"} /></label><label>Minimum charge (₹)<input name="minimumCharge" type="number" min="0" value={form.minimumCharge} onChange={update} /></label><label>Estimated duration (minutes)<input name="duration" type="number" min="1" value={form.duration} onChange={update} /></label><label>Description<textarea name="description" value={form.description} onChange={update} rows="3" /></label><button type="submit" disabled={saving || !form.categoryId}>{saving ? "Saving service..." : "Add service"}</button></form>}{message && <div className="my-services-message"><p role="alert">{message}</p><button type="button" onClick={() => { setMessage(""); load().catch((error) => setMessage(error.message)); }}>Reload services</button></div>}</section></main>;
}

export default MyServices;
