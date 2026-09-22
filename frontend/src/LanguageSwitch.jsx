import { useTranslation } from "react-i18next";
import "./LanguageSwitch.css";

export default function LanguageSwitch() {
  const { i18n } = useTranslation();
  return <nav className="language-switch" aria-label="Language / భాష">
    <button type="button" lang="en" aria-pressed={i18n.resolvedLanguage !== "te"} onClick={() => i18n.changeLanguage("en")}>English</button>
    <button type="button" lang="te" aria-pressed={i18n.resolvedLanguage === "te"} onClick={() => i18n.changeLanguage("te")}>తెలుగు</button>
  </nav>;
}
