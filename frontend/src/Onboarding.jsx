import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useState } from "react";
import { API_BASE_URL } from "./api";
import FarmSetup from "./FarmSetup";
import ProviderProfile from "./ProviderProfile";
import MyServices from "./MyServices";

// Derive progress from saved records so interrupted setup resumes on sign-in.
export default function Onboarding({ token, providerRegistration = false, onComplete, onBack }) {
  useTranslation();
  const [stage, setStage] = useState("loading");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    async function check() {
      const headers = { Authorization: `Bearer ${token}` };
      async function get(path) {
        const response = await fetch(`${API_BASE_URL}${path}`, { headers });
        if (!response.ok) throw new Error("Could not check your setup. Please retry.");
        return response.json();
      }
      const user = await get("/auth/me");
      const capabilities = user.capabilities || [];
      let next = "complete";
      if (providerRegistration) next = "profile";
      else if (!capabilities.includes("admin")) {
        if (capabilities.includes("provider")) {
          const services = await get("/supplier/services");
          if (!services.length) next = "profile";
        }
        if (next === "complete" && capabilities.includes("farmer")) {
          const farms = await get("/my/farms");
          const addresses = await get("/my/addresses");
          if (!farms.length) next = "farm";
          else if (!addresses.length) next = "address";
        }
      }
      if (!active) return;
      if (next === "complete") onComplete(user);
      else setStage(next);
    }
    check().catch((error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, [token, providerRegistration, attempt, onComplete]);

  async function finish() {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Could not refresh your account. Please retry.");
      onComplete(await response.json());
    } catch (error) { setMessage(error.message); }
  }

  return <>
    {stage === "farm" || stage === "address" && <FarmSetup token={token} onboarding addressOnly={stage === "address"} onBack={onBack} onFarmSaved={finish} />}
    {stage === "profile" && <ProviderProfile token={token} registration={providerRegistration} onboarding onBack={onBack} onRegistered={() => setStage("services")} />}
    {stage === "services" && <MyServices token={token} onboarding onBack={() => setStage("profile")} onComplete={finish} />}
    {stage === "loading" && !message && <p className="auth-message">{t("Checking your account setup...")}</p>}
    {message && <section className="auth-card"><p role="alert">{messageText(message)}</p><button className="primary-button" onClick={() => { setMessage(""); setStage("loading"); setAttempt((value) => value + 1); }}>{t("Retry setup check")}</button><button className="switch-mode" onClick={onBack}>{t("Back")}</button></section>}
  </>;
}
