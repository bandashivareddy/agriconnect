import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import te from "./locales/te.json";

export const languagePreferenceKey = "agriconnect.language";
export function readLanguage(storage) {
  try { return storage?.getItem(languagePreferenceKey) === "te" ? "te" : "en"; }
  catch { return "en"; }
}
export function saveLanguage(language, storage) {
  try { storage?.setItem(languagePreferenceKey, language === "te" ? "te" : "en"); }
  catch { /* The switch still works when browser storage is unavailable. */ }
}
function browserStorage() {
  try { return typeof window === "undefined" ? undefined : window.localStorage; }
  catch { return undefined; }
}

i18next.use(initReactI18next).init({
  resources: { en: { translation: en }, te: { translation: te } },
  lng: readLanguage(browserStorage()), fallbackLng: "en", supportedLngs: ["en", "te"],
  keySeparator: false, nsSeparator: false,
  interpolation: { escapeValue: false }, // React escapes rendered strings.
  react: { useSuspense: false },
});
i18next.on("languageChanged", (language) => {
  saveLanguage(language, browserStorage());
  if (typeof document !== "undefined") document.documentElement.lang = language;
});
if (typeof document !== "undefined") document.documentElement.lang = i18next.language;

export const t = (key, options) => i18next.t(key, options);
export const locale = () => i18next.resolvedLanguage === "te" ? "te-IN" : "en-IN";
// Client validation messages are kept as keys so visible errors also switch live.
// Unknown free-text backend errors remain unchanged; no guessing from SQL text.
export const messageText = (message) => !message ? "" : typeof message === "object" && message.key
  ? t(message.key, message.values) : t(String(message));
export default i18next;
