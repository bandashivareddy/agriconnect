import { useEffect, useState } from "react";
import { useCropApi, label } from "./cropApi";
import "./CropManagement.css";

const fields = [
  ["qualification", "Qualification", 300],
  ["crops_or_domains_known", "Crops or areas of work you know", 1000],
  ["operating_area_text", "Where you work", 500],
  ["languages_known", "Languages you speak", 300],
  ["notes", "Anything else you would like us to know", 2000],
];

export function OfficerApplicationFields({ value, onChange }) {
  return <fieldset className="officer-application-fields"><legend>Field Officer application</legend>
    <p>Application required. We will use your account name and contact details. The details below are optional.</p>
    <label>Years of experience (optional)<input type="number" min="0" max="80" step="0.1" value={value.experience_years ?? ""} onChange={(e) => onChange({ ...value, experience_years: e.target.value === "" ? null : Number(e.target.value) })} /></label>
    {fields.map(([key, title, max]) => <label key={key}>{title} (optional)<textarea maxLength={max} rows={2} value={value[key] || ""} onChange={(e) => onChange({ ...value, [key]: e.target.value.trim() ? e.target.value : null })} /></label>)}
    <p>Submitting an application does not give access to farms. An admin must approve it and assign your work separately.</p>
  </fieldset>;
}

function ApplicationDetails({ application }) {
  return <dl className="cm-summary">
    <div><dt>Applicant</dt><dd>{application.full_name}</dd></div>
    <div><dt>Mobile</dt><dd>{application.phone || "Not recorded"}</dd></div>
    {application.email && <div><dt>Email</dt><dd>{application.email}</dd></div>}
    <div><dt>Submitted</dt><dd>{new Date(application.created_at).toLocaleString()}</dd></div>
    {application.experience_years != null && <div><dt>Years of experience</dt><dd>{application.experience_years}</dd></div>}
    {fields.map(([key, title]) => application[key] && <div key={key}><dt>{title}</dt><dd className="cm-instructions">{application[key]}</dd></div>)}
    {application.reviewed_at && <div><dt>Reviewed</dt><dd>{new Date(application.reviewed_at).toLocaleString()} by {application.reviewer_name || "Admin"}</dd></div>}
    {application.rejection_reason && <div><dt>Reason</dt><dd className="cm-instructions">{application.rejection_reason}</dd></div>}
  </dl>;
}

export default function OfficerApplication({ token, user, onBack, onApproved }) {
  const api = useCropApi(token);
  const [application, setApplication] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { let active = true; api("/my/field-officer-application").then((data) => { if (active) { setApplication(data); setLoaded(true); setError(""); } }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, attempt]);
  async function submit(e) {
    e.preventDefault(); if (busy) return; setBusy(true); setError("");
    try { await api("/my/field-officer-application", "POST", form); setAttempt((n) => n + 1); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <main className="cm-page"><div className="cm-content"><header className="cm-row">{onBack && <button onClick={onBack}>Back</button>}<h1>Field Officer application</h1></header>
    {error && <p className="cm-error" role="alert">{error}</p>}
    <button disabled={busy} onClick={() => setAttempt((n) => n + 1)}>Refresh application status</button>
    {!loaded && !error && <p>Loading application...</p>}
    {application ? <section className="cm-card"><h2>{application.status === "pending" ? "Your Field Officer application is under review." : application.status === "approved" ? "Your application is approved." : "Your application was not approved."}</h2>
      <ApplicationDetails application={application} />
      {application.status === "pending" && <p>You can sign out and return later to check the decision.</p>}
      {application.status === "rejected" && <p>Resubmission is not available yet. Contact your administrator if you need a correction.</p>}
      {application.status === "approved" && <><p>You can open My Field Work. Farms appear only after an admin assigns your work.</p><button disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await onApproved(); } catch (err) { setError(err.message); } finally { setBusy(false); } }}>Open My Field Work</button></>}
    </section> : loaded && <section className="cm-card"><p>Applying as {user.full_name}. Your existing account and workspaces stay the same.</p>
      <form className="cm-form" onSubmit={submit}><OfficerApplicationFields value={form} onChange={setForm} /><button className="primary-button" disabled={busy}>Submit application</button></form></section>}
  </div></main>;
}

export function AdminOfficerApplications({ token, onBack, onAssignments }) {
  const api = useCropApi(token);
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState(null);
  const [selected, setSelected] = useState(null);
  const [decision, setDecision] = useState("approved");
  const [reason, setReason] = useState("");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; api(`/admin/field-officer-applications?status=${status}&offset=${offset}`).then((data) => { if (active) { setItems(data); setError(""); } }).catch((err) => { if (active) setError(err.message); }); return () => { active = false; }; }, [api, status, offset, attempt]);
  async function run(action) { if (busy) return; setBusy(true); setError(""); try { await action(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  return <main className="cm-page"><div className="cm-content"><header className="cm-row"><button onClick={() => selected ? setSelected(null) : onBack()}>Back</button><h1>Field Officer Applications</h1></header>
    {error && <p className="cm-error" role="alert">{error}</p>}
    <button disabled={busy} onClick={() => run(async () => { if (selected) setSelected(await api(`/admin/field-officer-applications/${selected.application_id}`)); else setAttempt((n) => n + 1); })}>Refresh</button>
    {selected ? <section className="cm-card"><h2>{label(selected.status)}</h2><ApplicationDetails application={selected} />
      {selected.status === "pending" && <form className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api(`/admin/field-officer-applications/${selected.application_id}/review`, "POST", { status: decision, rejection_reason: decision === "rejected" ? reason.trim() : null }); setSelected(await api(`/admin/field-officer-applications/${selected.application_id}`)); setAttempt((n) => n + 1); }); }}>
        <label>Decision<select value={decision} onChange={(e) => setDecision(e.target.value)}><option value="approved">Approve</option><option value="rejected">Reject</option></select></label>
        {decision === "rejected" && <label>Reason shown to applicant<textarea required maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
        <p>Approval enables My Field Work only. Crop assignments are a separate action.</p><button className="primary-button" disabled={busy}>Confirm decision</button>
      </form>}
      {selected.status === "approved" && <button onClick={onAssignments}>Manage Field Work / Assign a crop</button>}
    </section> : <><label>Application status<select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); setItems(null); }}>{["pending", "approved", "rejected"].map((s) => <option value={s} key={s}>{label(s)}</option>)}</select></label>
      {!items && !error && <p>Loading applications...</p>}{items?.length === 0 && <p>No applications in this status.</p>}
      {items?.map((a) => <article className="cm-card" key={a.application_id}><h2>{a.full_name}</h2><p>{a.phone || a.email} · {label(a.status)}</p><button disabled={busy} onClick={() => run(async () => { setSelected(await api(`/admin/field-officer-applications/${a.application_id}`)); setDecision("approved"); setReason(""); })}>Review application</button></article>)}
      <nav className="cm-row"><button disabled={!offset || busy} onClick={() => { setItems(null); setOffset((n) => n - 30); }}>Previous</button><button disabled={!items || items.length < 30 || busy} onClick={() => { setItems(null); setOffset((n) => n + 30); }}>Next</button></nav>
    </>}
  </div></main>;
}
