import { useEffect, useState } from "react";
import { displayDate, label, useCropApi } from "./cropApi";
import { VisitDetail } from "./FieldWork";
import "./CropManagement.css";

export default function FieldWorkAdmin({ token, onBack }) {
  const api = useCropApi(token);
  const [officers, setOfficers] = useState([]);
  const [users, setUsers] = useState([]);
  const [cycles, setCycles] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [visits, setVisits] = useState([]);
  const [selectedVisit, setSelectedVisit] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [offset, setOffset] = useState(0);
  const [userQuery, setUserQuery] = useState("");
  const [cycleQuery, setCycleQuery] = useState("");
  const [userId, setUserId] = useState("");
  const [assignmentForm, setAssignmentForm] = useState({ field_officer_id: "", farm_crop_id: "", notes: "" });
  const [scheduleForm, setScheduleForm] = useState({ assignment_id: "", planned_visit_date: "", visit_notes: "" });
  const [closing, setClosing] = useState(null);
  const [closeStatus, setCloseStatus] = useState("completed");
  const [closeNote, setCloseNote] = useState("");
  const [cancellingVisit, setCancellingVisit] = useState(null);
  const [cancelNote, setCancelNote] = useState("");
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try { const [os, cs, ass, vs] = await Promise.all([api("/admin/field-officers"), api("/admin/field-work/crop-cycles"), api(`/admin/field-work/assignments?offset=${offset}`), api(`/admin/field-work/visits?offset=${offset}`)]); if (active) { setOfficers(os); setCycles(cs); setAssignments(ass); setVisits(vs); setError(""); } }
      catch (err) { if (active) setError(err.message); }
      finally { if (active) setLoading(false); }
    }
    load(); return () => { active = false; };
  }, [api, attempt, offset]);
  async function run(work) { if (busy) return; setBusy(true); setError(""); try { await work(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  function refresh() { setAttempt((n) => n + 1); }
  return <main className="cm-page"><div className="cm-content"><header className="cm-row"><button onClick={() => selectedVisit ? setSelectedVisit(null) : onBack()}>← {selectedVisit ? "Field operations" : "Admin dashboard"}</button><h1>Field operations</h1></header>
    {error && <p className="cm-error" role="alert">{error}</p>}{selectedVisit ? <VisitDetail key={selectedVisit} api={api} id={selectedVisit} readOnly pathPrefix="/admin/field-work/visits" /> : <>
    <p>Review new applicants in Field Officer Applications. For existing staff accounts, enable field access, assign a crop, and schedule a visit. Assignment access is limited to that crop.</p><button onClick={refresh} disabled={busy}>Refresh field operations</button>
    <section className="cm-card"><h2>Enable Field Officer access</h2><form className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { setUsers(await api(`/admin/field-work/users?q=${encodeURIComponent(userQuery)}`)); setUserId(""); }); }}>
      <label>Find an existing account by name, mobile or email<input value={userQuery} onChange={(e) => setUserQuery(e.target.value)} maxLength="100" /></label><button disabled={busy}>Search accounts</button>
    </form>{users.length > 0 && <form className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/field-officers", "POST", { user_id: Number(userId) }); setUsers([]); setUserId(""); refresh(); }); }}>
      <label>Account<select value={userId} onChange={(e) => setUserId(e.target.value)} required><option value="">Select account</option>{users.map((u) => <option key={u.user_id} value={u.user_id}>{u.full_name} · #{u.user_id} · {u.user_role === "supplier" ? "Service Provider" : u.user_role === "member" ? "Account" : label(u.user_role)}{u.is_field_officer ? " · already Field Officer" : ""}</option>)}</select></label><p>Existing workspaces remain unchanged. This alone gives no access to any farm.</p><button disabled={busy}>Enable Field Officer for this account</button>
    </form>}</section>
    <section className="cm-card"><h2>Assign officer to Crop Cycle</h2><form className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { setCycles(await api(`/admin/field-work/crop-cycles?q=${encodeURIComponent(cycleQuery)}&limit=100`)); setAssignmentForm((old) => ({ ...old, farm_crop_id: "" })); }); }}>
      <label>Find crop cycles by farmer, farm or crop<input value={cycleQuery} onChange={(e) => setCycleQuery(e.target.value)} /></label><button disabled={busy}>Search crop cycles</button></form>
      <form className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/field-work/assignments", "POST", { field_officer_id: Number(assignmentForm.field_officer_id), farm_crop_id: Number(assignmentForm.farm_crop_id), notes: assignmentForm.notes || null }); setAssignmentForm({ field_officer_id: "", farm_crop_id: "", notes: "" }); setOffset(0); refresh(); }); }}>
        <label>Field Officer<select value={assignmentForm.field_officer_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, field_officer_id: e.target.value })} required><option value="">Select officer</option>{officers.map((o) => <option key={o.user_id} value={o.user_id}>{o.full_name} · #{o.user_id}</option>)}</select></label>
        <label>Crop Cycle<select value={assignmentForm.farm_crop_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, farm_crop_id: e.target.value })} required><option value="">Select cultivation instance</option>{cycles.map((c) => <option key={c.farm_crop_id} value={c.farm_crop_id}>#{c.farm_crop_id} · {c.farmer_name} · {c.farm_name} / {c.plot_name} · {c.crop_name} · {label(c.status)}</option>)}</select></label>
        <label>Assignment notes<textarea value={assignmentForm.notes} onChange={(e) => setAssignmentForm({ ...assignmentForm, notes: e.target.value })} /></label><button className="primary-button" disabled={busy || loading}>Assign officer</button>
      </form></section>
    <section className="cm-card"><h2>Schedule visit</h2><form className="cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/admin/field-work/visits", "POST", { ...scheduleForm, assignment_id: Number(scheduleForm.assignment_id), visit_notes: scheduleForm.visit_notes || null }); setScheduleForm({ assignment_id: "", planned_visit_date: "", visit_notes: "" }); refresh(); }); }}>
      <label>Active assignment<select value={scheduleForm.assignment_id} onChange={(e) => setScheduleForm({ ...scheduleForm, assignment_id: e.target.value })} required><option value="">Select assignment</option>{assignments.filter((a) => a.status === "active").map((a) => <option key={a.assignment_id} value={a.assignment_id}>#{a.assignment_id} · {a.officer_name} · {a.farm_name} / {a.plot_name} · {a.crop_name}</option>)}</select></label>
      <label>Planned visit date<input type="date" value={scheduleForm.planned_visit_date} onChange={(e) => setScheduleForm({ ...scheduleForm, planned_visit_date: e.target.value })} required /></label>
      <label>Visit notes<textarea value={scheduleForm.visit_notes} onChange={(e) => setScheduleForm({ ...scheduleForm, visit_notes: e.target.value })} /></label><button disabled={busy || loading}>Schedule visit</button>
    </form></section>
    <h2>Assignments</h2>{loading && <p>Loading assignments...</p>}{assignments.map((a) => <article className="cm-card" key={a.assignment_id}><h3>{a.officer_name} · {a.crop_name}</h3><p>{a.farmer_name} · {a.farm_name} / {a.plot_name}</p><p>Assignment #{a.assignment_id} · {label(a.status)}</p>{a.notes && <p>{a.notes}</p>}{a.status === "active" && <button disabled={busy} onClick={() => { setClosing(a); setCloseNote(a.notes || ""); }}>Close assignment</button>}</article>)}
    {closing && <form className="cm-card cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api(`/admin/field-work/assignments/${closing.assignment_id}`, "PATCH", { expected_status: closing.status, status: closeStatus, notes: closeNote || null }); setClosing(null); refresh(); }); }}><h3>Close assignment #{closing.assignment_id}</h3><p>The officer loses access immediately. Unfinished visits are cancelled; observations and history remain available to the farmer and admins.</p><label>Close as<select value={closeStatus} onChange={(e) => setCloseStatus(e.target.value)}><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label><label>Notes<textarea value={closeNote} onChange={(e) => setCloseNote(e.target.value)} /></label><div className="cm-row"><button type="button" onClick={() => setClosing(null)}>Keep active</button><button disabled={busy}>Confirm closure</button></div></form>}
    <h2>Visits</h2>{visits.map((v) => <article className="cm-card" key={v.visit_id}><h3>{v.officer_name} · {v.crop_name}</h3><p>{v.farm_name} / {v.plot_name} · {displayDate(v.planned_visit_date)} · {label(v.status)}</p><div className="cm-row"><button onClick={() => setSelectedVisit(v.visit_id)}>Read visit</button>{["planned", "in_progress"].includes(v.status) && <button disabled={busy} onClick={() => { setCancellingVisit(v); setCancelNote(""); }}>Cancel visit</button>}</div></article>)}
    {cancellingVisit && <form className="cm-card cm-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api(`/admin/field-work/visits/${cancellingVisit.visit_id}/cancel`, "POST", { expected_status: cancellingVisit.status, status: "cancelled", visit_notes: cancelNote }); setCancellingVisit(null); refresh(); }); }}><h3>Cancel visit #{cancellingVisit.visit_id}</h3><label>Reason<textarea value={cancelNote} onChange={(e) => setCancelNote(e.target.value)} required /></label><button disabled={busy}>Confirm cancellation</button><button type="button" onClick={() => setCancellingVisit(null)}>Keep visit</button></form>}
    <nav className="cm-row" aria-label="Field operations pages"><button disabled={offset === 0 || loading} onClick={() => setOffset((n) => n - 50)}>Previous</button><span>Page {offset / 50 + 1}</span><button disabled={loading || (assignments.length < 50 && visits.length < 50)} onClick={() => setOffset((n) => n + 50)}>Next</button></nav>
    </>}
  </div></main>;
}
