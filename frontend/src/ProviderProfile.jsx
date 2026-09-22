import { useCallback, useEffect, useState } from "react";
import "./ProviderProfile.css";
import { API_BASE_URL, apiError } from "./api";

const API_URL = API_BASE_URL;

const emptyForm = {
  business_name: "",
  description: "",
  business_registration_no: "",
  gstin: "",
};

function ProviderProfile({ token, onBack, registration = false, onRegistered, onboarding = false }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(registration || onboarding);
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const loadProfile = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/provider/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.status === 404) {
        setProfile(null);
        return;
      }
      if (!response.ok) throw new Error(apiError(data, "Could not load provider profile."));
      setProfile(data);
      if (onboarding) setForm({ ...emptyForm, ...data });
    } catch (error) {
      console.error(error);
      setMessage(error.message || "Could not load provider profile.");
    } finally {
      setLoading(false);
    }
  }, [token, onboarding]);

  useEffect(() => {
    async function fetchInitialProfile() {
      await loadProfile(false);
    }

    fetchInitialProfile();
  }, [loadProfile]);

  function openForm() {
    setMessage("");
    setForm(profile ? {
      business_name: profile.business_name || "",
      description: profile.description || "",
      business_registration_no: profile.business_registration_no || "",
      gstin: profile.gstin || "",
    } : emptyForm);
    setShowForm(true);
  }

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function saveProfile(event) {
    event.preventDefault();
    setMessage("");
    if (form.business_name.trim().length < 2) {
      setMessage("Provider / Business name must have at least 2 characters.");
      return;
    }
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/provider/profile`, {
        method: profile ? "PUT" : "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          business_name: form.business_name.trim(),
          description: form.description || null,
          business_registration_no: form.business_registration_no || null,
          gstin: form.gstin || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(apiError(data, "Could not save provider profile."));
      if ((registration || onboarding) && onRegistered) {
        onRegistered();
        return;
      }
      await loadProfile();
      setShowForm(false);
    } catch (error) {
      console.error(error);
      setMessage(error.message || "Could not save provider profile.");
    } finally {
      setSaving(false);
    }
  }

  return <main className="provider-profile-page"><section className="provider-profile-content">
    <div className="provider-profile-topbar"><button className="provider-profile-back" type="button" onClick={onBack} aria-label={registration ? "Back to farmer page" : "Back to Provider Dashboard"}>←</button><h1>{registration ? "Become a Provider" : "Provider Profile"}</h1><div aria-hidden="true" /></div>
    <p className="provider-profile-intro">Manage your provider and business information.</p>
    {loading ? <p className="provider-profile-loading">Loading provider profile...</p> : profile ? <section className="provider-profile-card">
      <h2>{profile.business_name}</h2>
      <p className="provider-profile-description">{profile.description || "No description provided."}</p>
      <dl><div><dt>Business registration</dt><dd>{profile.business_registration_no || "Not provided"}</dd></div><div><dt>GSTIN</dt><dd>{profile.gstin || "Not provided"}</dd></div></dl>
      <button className="secondary-action provider-profile-edit" type="button" onClick={openForm}>Edit →</button>
    </section> : <section className="provider-profile-card provider-profile-empty"><h2>No provider profile has been set up yet.</h2><p>Add your provider details so your services can represent you correctly.</p><button className="primary-button provider-profile-setup" type="button" onClick={openForm}>+ Set Up Profile</button></section>}
    {showForm && <section className="provider-profile-form-card"><h2>{profile ? "Edit Provider Profile" : "Set Up Provider Profile"}</h2><form onSubmit={saveProfile}>
      <label>Provider / Business name<input name="business_name" value={form.business_name} onChange={updateField} minLength="2" maxLength="150" required /></label>
      <label>Description (optional)<textarea name="description" value={form.description} onChange={updateField} rows="4" /></label>
      <label>Business registration number (optional)<input name="business_registration_no" value={form.business_registration_no} onChange={updateField} /></label>
      <label>GSTIN (optional)<input name="gstin" value={form.gstin} onChange={updateField} /></label>
      <button className="primary-button" type="submit" disabled={saving}>{saving ? "Saving profile..." : profile ? "Save changes" : "Create profile"}</button>
    </form></section>}
    {message && <p className="provider-profile-message">{message}</p>}
  </section></main>;
}

export default ProviderProfile;
