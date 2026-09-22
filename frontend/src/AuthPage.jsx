import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useState } from "react";
import "./AuthPage.css";
import { API_BASE_URL, apiError } from "./api";

import { OfficerApplicationFields } from "./OfficerApplications";

const API_URL = API_BASE_URL;

function AuthPage({ onLogin, onBack }) {
  useTranslation();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    identifier: "",
    phone: "",
    password: "",
    userRole: "farmer",
    businessName: "",
  });
  const [application, setApplication] = useState({});
  const [roleOptions, setRoleOptions] = useState([]);
  const [roleError, setRoleError] = useState("");
  const [roleAttempt, setRoleAttempt] = useState(0);
  useEffect(() => {
    if (mode !== "register") return;
    let active = true;
    fetch(`${API_URL}/auth/signup-options`).then(async (response) => { if (!response.ok) throw new Error("Could not load signup options."); return response.json(); }).then((data) => { if (active) { setRoleOptions(data); setRoleError(""); } }).catch((err) => { if (active) setRoleError(err.message); });
    return () => { active = false; };
  }, [mode, roleAttempt]);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function submitForm(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setMessage("");

    try {
      if (mode === "register") {
        const response = await fetch(`${API_URL}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: form.fullName,
            email: form.email.trim() || null,
            phone: form.phone || null,
            password: form.password,
            signup_intent: form.userRole,
            ...(form.userRole === "field_officer" ? { field_officer_application: application } : {}),
            business_name:
              form.userRole === "provider" ? form.businessName || null : null,
          }),
        });

        const result = await response.json();

        if (!response.ok) {
          throw new Error(apiError(result, "Account could not be created."));
        }

        setMode("login");
        setForm((current) => ({ ...current, identifier: current.phone || current.email }));
      }

      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(mode === "register"
            ? (form.phone ? { phone: form.phone } : { email: form.email })
            : (form.identifier.includes("@") ? { email: form.identifier.trim() } : { phone: form.identifier })),
          password: form.password,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(apiError(result, "Sign-in failed."));
      }

      onLogin(result.access_token, result.user);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <button className="back-button" onClick={onBack}>{t("← Back to marketplace")}</button>

      <section className="auth-card">
        <p className="eyebrow">{t("AgriConnect account")}</p>
        <h1>{mode === "login" ? t("Welcome back") : t("Create your account")}</h1>
        <p>
          {mode === "login" ? t("Sign in to manage your bookings and services.") : t("Choose how you want to use AgriConnect. One account can support different kinds of work.")}
        </p>

        <form onSubmit={submitForm} className="auth-form">
          {mode === "register" && <>
              <label>{t("Full name")}<input
                  name="fullName"
                  value={form.fullName}
                  onChange={updateField}
                  required
                />
              </label>

              <fieldset className="signup-roles"><legend>{t("How do you want to use AgriConnect?")}</legend>
                {roleOptions.map((role) => <label className="signup-role-card" key={role.code}><input type="radio" name="userRole" value={role.code} checked={form.userRole === role.code} onChange={updateField} /><span><strong>{role.label}</strong><span>{role.description}</span>{role.notice && <small>{role.notice}</small>}</span></label>)}
                {roleError && <p role="alert">{messageText(roleError)} <button type="button" onClick={() => setRoleAttempt((n) => n + 1)}>{t("Retry")}</button></p>}
                {!roleOptions.length && !roleError && <p>{t("Loading signup options...")}</p>}
              </fieldset>
              {form.userRole === "field_officer" && <OfficerApplicationFields value={application} onChange={setApplication} />}
              {form.userRole === "landowner" && <p>{t("Managed farming is coming later. This account records your interest and does not start a managed farming service.")}</p>}

              {form.userRole === "provider" && <label>{t("Business name")}<input
                    required
                    minLength="2"
                    name="businessName"
                    value={form.businessName}
                    onChange={updateField}
                  />
                </label>}

              <label>{t("Mobile number")}<input
                  type="tel"
                  autoComplete="tel"
                  required={!form.email.trim()}
                  name="phone"
                  value={form.phone}
                  onChange={updateField}
                />
              </label>
            </>}

          <label>
            {mode === "register" ? t("Email address (optional)") : t("Mobile number or email")}
            <input
              name={mode === "register" ? "email" : "identifier"}
              type={mode === "register" ? "email" : "text"}
              autoComplete={mode === "register" ? "email" : "username"}
              value={mode === "register" ? form.email : form.identifier}
              onChange={updateField}
              required={mode === "login"}
            />
          </label>

          <label>{t("Password")}<input
              name="password"
              type="password"
              minLength="8"
              value={form.password}
              onChange={updateField}
              required
            />
          </label>

          <button className="primary-button" disabled={submitting || (mode === "register" && !roleOptions.length)}>
            {submitting ? t("Please wait…") : mode === "login" ? t("Sign in") : form.userRole === "field_officer" ? t("Create account and submit application") : t("Create account")}
          </button>
        </form>

        {message && <p className="auth-message">{messageText(message)}</p>}

        <button
          className="switch-mode"
          onClick={() => {
            setMessage("");
            setMode(mode === "login" ? "register" : "login");
          }}
        >
          {mode === "login" ? t("New here? Create an account") : t("Already have an account? Sign in")}
        </button>
      </section>
    </main>
  );
}

export default AuthPage;
