import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useCropApi } from "./cropApi";
import { CropListCard } from "./CropManagement";
import "./CropManagement.css";

function CurrentCrops({ api, farmId, onOpenCrop }) {
  const [cycles, setCycles] = useState(null);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api(`/my/crop-cycles?farm_id=${farmId}&view=current&limit=20&offset=${offset}`)
      .then((data) => { if (active) setCycles(data); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, farmId, offset, attempt]);
  function page(next) { setCycles(null); setError(""); setOffset(next); }
  return <section aria-labelledby="growing-now">
    <h2 id="growing-now">{t("Growing now")}</h2>
    {error ? <p role="alert">{messageText(error)} <button onClick={() => { setError(""); setAttempt((n) => n + 1); }}>{t("Retry")}</button></p>
      : cycles === null ? <p role="status">{t("Loading crops...")}</p>
        : cycles.length === 0 ? <p>{t("No current crops")}</p>
          : cycles.map((cycle) => <CropListCard key={cycle.farm_crop_id} cycle={cycle} onOpen={() => onOpenCrop(cycle.farm_crop_id)} />)}
    {(offset > 0 || cycles?.length === 20) && <nav className="cm-row" aria-label={t("Crop pages")}>
      <button disabled={!offset || cycles === null} onClick={() => page(offset - 20)}>{t("Previous")}</button>
      <button disabled={cycles === null || cycles.length < 20} onClick={() => page(offset + 20)}>{t("Next")}</button>
    </nav>}
  </section>;
}

export default function FarmerWorkspace({ token, selectedFarmId, onSelectFarm, onBack, onManageFarm, onOpenCrop }) {
  useTranslation();
  const api = useCropApi(token);
  const [farms, setFarms] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api("/my/farms").then((data) => { if (active) setFarms(data); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [api, attempt]);
  const farm = farms?.find((entry) => entry.farm_id === selectedFarmId) || farms?.[0];
  return <main className="cm-page"><div className="cm-content">
    <header className="cm-row"><button onClick={onBack}>{t("Home")}</button><h1>{t("My Farm")}</h1></header>
    {error ? <p role="alert">{messageText(error)} <button onClick={() => { setError(""); setAttempt((n) => n + 1); }}>{t("Retry")}</button></p>
      : farms === null ? <p role="status">{t("Loading farms...")}</p>
        : !farm ? <section className="cm-card"><h2>{t("No farms yet")}</h2><button onClick={onManageFarm}>{t("Add Farm")}</button></section>
          : <>
            {farms.length > 1 ? <label>{t("Farm")}<select value={farm.farm_id} onChange={(event) => onSelectFarm(Number(event.target.value))}>
              {farms.map((entry) => <option key={entry.farm_id} value={entry.farm_id}>{entry.farm_name}</option>)}
            </select></label> : <h2>{farm.farm_name}</h2>}
            <CurrentCrops key={farm.farm_id} api={api} farmId={farm.farm_id} onOpenCrop={onOpenCrop} />
          </>}
    <footer><button onClick={onManageFarm}>{t("Manage Farm")}</button></footer>
  </div></main>;
}
