import { useCallback, useEffect, useState } from "react";
import "./ProviderVerification.css";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;
const emptyForm = { documentType: "", file: null };

function ProviderVerification({ token, onBack }) {
  const [profile, setProfile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const loadVerification = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const [profileResponse, documentsResponse] = await Promise.all([
        fetch(`${API_URL}/provider/profile`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_URL}/provider/documents`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      const [profileData, documentsData] = await Promise.all([profileResponse.json(), documentsResponse.json()]);
      if (!profileResponse.ok) throw new Error(profileData.detail || "Could not load provider verification status.");
      if (!documentsResponse.ok || !Array.isArray(documentsData)) throw new Error(documentsData.detail || "Could not load verification documents.");
      setProfile(profileData);
      setDocuments(documentsData);
    } catch (error) {
      console.error(error);
      setMessage(error.message || "Could not load provider verification.");
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { async function load() { await loadVerification(false); } load(); }, [loadVerification]);

  function updateField(event) { const { name, value } = event.target; setForm((current) => ({ ...current, [name]: value })); }
  function chooseFile(event) { setForm((current) => ({ ...current, file: event.target.files?.[0] || null })); }
  async function submitDocument(event) {
    event.preventDefault(); setMessage(""); setSaving(true);
    try {
      if (!form.file) throw new Error("Choose a PDF, JPEG, or PNG document.");
      const upload = new FormData(); upload.append("document_type", form.documentType); upload.append("file", form.file);
      const response = await fetch(`${API_URL}/provider/documents`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: upload });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Verification document could not be submitted.");
      await loadVerification(); setForm(emptyForm); setShowForm(false); setMessage("Document submitted for verification.");
    } catch (error) { console.error(error); setMessage(error.message || "Verification document could not be submitted."); }
    finally { setSaving(false); }
  }

  return <main className="provider-verification-page"><section className="provider-verification-content">
    <div className="provider-verification-topbar"><button className="provider-verification-back" type="button" onClick={onBack} aria-label="Back to Provider Dashboard">←</button><h1>Verification</h1><div aria-hidden="true" /></div>
    <p className="provider-verification-intro">Verify your provider account and manage supporting documents.</p>
    {loading ? <p className="provider-verification-loading">Loading verification details...</p> : <>
      <section className="provider-verification-status"><h2>Verification Status</h2><strong className={profile?.verified_at ? "verification-state verified" : "verification-state pending"}>{profile?.verified_at ? "Verified" : "Pending Verification"}</strong><p>{profile?.verified_at ? "Your provider account has been verified." : "Verification is completed after an administrator reviews your submitted documents."}</p></section>
      <section className="provider-document-list">{documents.length === 0 ? <div className="provider-document-empty"><strong>No verification documents submitted.</strong><p>Add a qualifying document for admin review.</p></div> : documents.map((document) => <article className="provider-document-card" key={document.document_id}><div><h3>{document.document_type_label || document.document_type}</h3><p>{document.file_name}</p><p>{document.has_uploaded_file ? "Secure file uploaded" : <><strong>Document reference:</strong> {document.file_url}</>}</p></div><span className={`provider-document-status provider-document-status-${document.verification_status}`}>{document.verification_status}</span></article>)}</section>
      <p className="provider-verification-help">To become eligible for provider verification, submit at least one qualifying identity, vehicle/equipment, or service/trade document. GST registration and business registration are optional.</p>
      <button className="primary-button provider-document-add" type="button" onClick={() => { setMessage(""); setShowForm((current) => !current); }}>{showForm ? "Close" : "+ Add Document"}</button>
      {showForm && <section className="provider-document-form-card"><h2>Add Document</h2><form onSubmit={submitDocument}>
        <label>Document type<select name="documentType" value={form.documentType} onChange={updateField} required><option value="" disabled>Select a document type</option><optgroup label="Identity / Qualification"><option value="driving_licence">Driving Licence</option><option value="voter_id">Voter ID</option><option value="other_government_id">Other Government ID</option><option value="service_trade_certificate">Service / Trade Certificate</option></optgroup><optgroup label="Equipment"><option value="vehicle_equipment_rc">Vehicle / Equipment RC</option><option value="equipment_ownership_proof">Equipment Ownership Proof</option></optgroup><optgroup label="Business / Supporting"><option value="gst_certificate">GST Certificate</option><option value="business_registration">Business Registration</option><option value="other_supporting_document">Other Supporting Document</option></optgroup></select></label>
        <label>Choose file<input name="file" type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" onChange={chooseFile} required /></label>
        {form.file && <p className="provider-document-note">Selected: {form.file.name} ({Math.ceil(form.file.size / 1024)} KB)</p>}
        <p className="provider-document-note">PDF, JPEG, or PNG only. Maximum file size: 5 MB.</p>
        <button className="primary-button" type="submit" disabled={saving}>{saving ? "Submitting document..." : "Submit for verification"}</button>
      </form></section>}
    </>}
    {message && <p className="provider-verification-message">{message}</p>}
  </section></main>;
}
export default ProviderVerification;
