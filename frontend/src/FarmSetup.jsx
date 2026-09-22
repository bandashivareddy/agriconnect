import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import React, { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "./api";
import { cropStatusLabel } from "./farmerLabels";
import { useCropApi } from "./cropApi";
import { BlockManager, FarmWorkspace } from "./FarmLedger";
import "./CropManagement.css";

const API_URL = API_BASE_URL;

function FarmSetup({ token, onBack, onFarmSaved, onStartCrop, onboarding = false, addressOnly = false }) {
  useTranslation();
  const cropApi = useCropApi(token);
  const createdFarm = useRef(null);
  const [setupComplete, setSetupComplete] = useState(false);
  const [savedPlotId, setSavedPlotId] = useState(null);

  const [blockPlotId, setBlockPlotId] = useState(null);
  const [showFarmRecords, setShowFarmRecords] = useState(false);
  const [farmCreated, setFarmCreated] = useState(addressOnly);
  const [farms, setFarms] = useState([]);
  const [loading, setLoading] = useState(true);

  const [showAddFarm, setShowAddFarm] = useState(onboarding);

  const [selectedFarm, setSelectedFarm] = useState(null);
  const [farmDetails, setFarmDetails] = useState(null);
  useEffect(() => { if (savedPlotId && farmDetails) document.getElementById(`farm-plot-${savedPlotId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [savedPlotId, farmDetails]);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const [showAddPlot, setShowAddPlot] = useState(false);
  const [savingPlot, setSavingPlot] = useState(false);

  const [showAddCrop, setShowAddCrop] = useState(false);
  const [savingCrop, setSavingCrop] = useState(false);
  const [cropCatalogue, setCropCatalogue] = useState([]);
  const [cropCatalogueLoading, setCropCatalogueLoading] = useState(false);

  const [saving, setSaving] = useState(false);

  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const [farm, setFarm] = useState({
    farmName: "",
    location: "",
    totalAreaAcres: "",
  });

  const [address, setAddress] = useState({
    label: "",
    addressLine1: "",
    villageOrCity: "",
    district: "",
    state: "",
    postalCode: "",
  });

  const [plot, setPlot] = useState({
    plotName: "",
    areaAcres: "",
    soilType: "",
    irrigationType: "",
  });

  const [crop, setCrop] = useState({
    plotId: "",
    cropId: "",
    season: "",
    plantedOn: "",
    expectedHarvestOn: "",
  });

  useEffect(() => {
    loadFarms();
  }, []);

  async function loadFarms() {
    try {
      setLoading(true);
      setErrorMessage("");

      const response = await fetch(`${API_URL}/my/farms`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        throw new Error(
          errorData.detail || "Unable to load farms."
        );
      }

      const data = await response.json();
      setFarms(data);
    } catch (error) {
      console.error(error);

      setErrorMessage(
        error.message || "Unable to load farms."
      );
    } finally {
      setLoading(false);
    }
  }

  async function openFarmDetails(farmItem) {
    try {
      setSelectedFarm(farmItem);
      setFarmDetails(null);
      setDetailsLoading(true);

      setMessage("");
      setErrorMessage("");

      setShowAddPlot(false);
      setShowAddCrop(false);

      const response = await fetch(
        `${API_URL}/my/farms/${farmItem.farm_id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        throw new Error(
          errorData.detail || "Unable to load farm details."
        );
      }

      const data = await response.json();
      setFarmDetails(data);
    } catch (error) {
      console.error(error);

      setErrorMessage(
        error.message || "Unable to load farm details."
      );
    } finally {
      setDetailsLoading(false);
    }
  }

  function closeFarmDetails() {
    setSelectedFarm(null);
    setFarmDetails(null);

    setShowAddPlot(false);
    setShowAddCrop(false);

    setMessage("");
    setErrorMessage("");
  }

  function openAddPlot() {
    setPlot({
      plotName: "",
      areaAcres: "",
      soilType: "",
      irrigationType: "",
    });

    setMessage("");
    setErrorMessage("");

    setShowAddCrop(false);
    setShowAddPlot(true);
  }

  function closeAddPlot() {
    setShowAddPlot(false);

    setMessage("");
    setErrorMessage("");
  }

  async function savePlot(event) {
    event.preventDefault();

    setMessage("");
    setErrorMessage("");

    if (!plot.plotName.trim()) {
      setErrorMessage("Please enter a plot name.");
      return;
    }

    if (
      plot.areaAcres &&
      Number(plot.areaAcres) <= 0
    ) {
      setErrorMessage(
        "Plot area must be greater than zero."
      );
      return;
    }

    if (!selectedFarm) {
      setErrorMessage("No farm selected.");
      return;
    }

    try {
      setSavingPlot(true);

      const response = await fetch(
        `${API_URL}/my/farms/${selectedFarm.farm_id}/plots`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            farm_id: selectedFarm.farm_id,
            plot_name: plot.plotName.trim(),
            area_acres: plot.areaAcres
              ? Number(plot.areaAcres)
              : null,
            soil_type: plot.soilType.trim() || null,
            irrigation_type:
              plot.irrigationType.trim() || null,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        throw new Error(
          errorData.detail || "Unable to create plot."
        );
      }

      const savedPlot = await response.json();
      setSavedPlotId(savedPlot.plot_id);
      setMessage("Plot added successfully.");

      await openFarmDetails(selectedFarm);

      setShowAddPlot(false);
    } catch (error) {
      console.error(error);

      setErrorMessage(
        error.message || "Unable to create plot."
      );
    } finally {
      setSavingPlot(false);
    }
  }

  async function loadCropCatalogue() {
    try {
      setCropCatalogueLoading(true);
      setErrorMessage("");

      const response = await fetch(
        `${API_URL}/crops`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        throw new Error(
          errorData.detail ||
            "Unable to load crop catalogue."
        );
      }

      const data = await response.json();

      setCropCatalogue(data);
    } catch (error) {
      console.error(error);

      setErrorMessage(
        error.message ||
          "Unable to load crop catalogue."
      );
    } finally {
      setCropCatalogueLoading(false);
    }
  }

  async function openAddCrop() {
    if (onStartCrop) { onStartCrop({ farm_id: selectedFarm.farm_id }); return; }
    setCrop({
      plotId: "",
      cropId: "",
      season: "",
      plantedOn: "",
      expectedHarvestOn: "",
    });

    setMessage("");
    setErrorMessage("");

    setShowAddPlot(false);
    setShowAddCrop(true);

    if (cropCatalogue.length === 0) {
      await loadCropCatalogue();
    }
  }

  function closeAddCrop() {
    setShowAddCrop(false);

    setMessage("");
    setErrorMessage("");
  }

  async function saveCrop(event) {
    event.preventDefault();

    setMessage("");
    setErrorMessage("");

    if (!selectedFarm) {
      setErrorMessage("No farm selected.");
      return;
    }

    if (!crop.plotId) {
      setErrorMessage("Please select a plot.");
      return;
    }

    if (!crop.cropId) {
      setErrorMessage("Please select a crop.");
      return;
    }

    if (
      crop.plantedOn &&
      crop.expectedHarvestOn &&
      crop.expectedHarvestOn < crop.plantedOn
    ) {
      setErrorMessage(
        "Expected harvest date cannot be before the planted date."
      );
      return;
    }

    try {
      setSavingCrop(true);

      const response = await fetch(
        `${API_URL}/my/farms/${selectedFarm.farm_id}/crops`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            farm_id: selectedFarm.farm_id,
            plot_id: Number(crop.plotId),
            crop_id: Number(crop.cropId),
            season: crop.season.trim() || null,
            planted_on: crop.plantedOn || null,
            expected_harvest_on:
              crop.expectedHarvestOn || null,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        throw new Error(
          errorData.detail || "Unable to add crop."
        );
      }

      setShowAddCrop(false);
      setMessage("Crop added successfully.");

      await openFarmDetails(selectedFarm);
    } catch (error) {
      console.error(error);

      setErrorMessage(
        error.message || "Unable to add crop."
      );
    } finally {
      setSavingCrop(false);
    }
  }

  function openAddFarm() {
    setMessage("");
    setErrorMessage("");

    setFarm({
      farmName: "",
      location: "",
      totalAreaAcres: "",
    });

    setAddress({
      label: "",
      addressLine1: "",
      villageOrCity: "",
      district: "",
      state: "",
      postalCode: "",
    });

    setShowAddFarm(true);
  }

  function closeAddFarm() {
    setShowAddFarm(false);

    setMessage("");
    setErrorMessage("");
  }

  async function saveSetup(event) {
    event.preventDefault();

    setMessage("");
    setErrorMessage("");

    if (!farmCreated && !farm.farmName.trim()) {
      setErrorMessage("Please enter a farm name.");
      return;
    }

    if (!farmCreated && !farm.location.trim()) {
      setErrorMessage("Please enter the farm location.");
      return;
    }

    if (
      !farmCreated && (!farm.totalAreaAcres ||
      Number(farm.totalAreaAcres) <= 0)
    ) {
      setErrorMessage(
        "Please enter a valid farm area."
      );
      return;
    }

    try {
      setSaving(true);

      if (onboarding && [address.addressLine1, address.villageOrCity, address.state].some((value) => value.trim().length < 2)) {
        throw new Error("Enter an address, village/city and state (at least 2 characters each).");
      }
      if (!farmCreated) {
      const farmResponse = await fetch(
        `${API_URL}/farms`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            farm_name: farm.farmName.trim(),
            location: farm.location.trim(),
            total_area_acres: Number(
              farm.totalAreaAcres
            ),
          }),
        }
      );

      if (!farmResponse.ok) {
        const errorData = await farmResponse.json().catch(
          () => ({})
        );

        throw new Error(
          errorData.detail || "Unable to create farm."
        );
      }

      createdFarm.current = await farmResponse.json();
      setFarmCreated(true);
      }

      const hasAddress =
        address.addressLine1.trim() ||
        address.villageOrCity.trim() ||
        address.district.trim() ||
        address.state.trim() ||
        address.postalCode.trim();

      if (hasAddress) {
        const addressResponse = await fetch(
          `${API_URL}/addresses`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              label:
                address.label.trim() || "Farm Address",
              address_line1:
                address.addressLine1.trim(),
              village_or_city:
                address.villageOrCity.trim(),
              district: address.district.trim(),
              state: address.state.trim(),
              postal_code:
                address.postalCode.trim(),
              is_default: true,
            }),
          }
        );

        if (!addressResponse.ok) {
          throw new Error("Your farm is saved, but the address could not be saved. Check the address and retry.");
        }
      }

      await loadFarms();

      setFarmCreated(false);
      setShowAddFarm(false);
      setMessage("Farm and address saved successfully.");

      if (createdFarm.current) {
        await openFarmDetails(createdFarm.current);
        if (onboarding) setSetupComplete(true);
      } else if (onFarmSaved) {
        onFarmSaved();
      }
    } catch (error) {
      console.error(error);

      setErrorMessage(
        error.message || "Unable to save farm."
      );
    } finally {
      setSaving(false);
    }
  }

  /*
   * Loading My Farms
   */
  if (loading) {
    return (
      <div style={styles.page}>
        <div style={styles.container}>
          <div style={styles.topBar}>
            <button
              onClick={onBack}
              style={styles.backButton}
            >
              ←
            </button>

            <h1 style={styles.title}>{t("My Farms")}</h1>

            <div style={{ width: 40 }} />
          </div>

          <div style={styles.loadingCard}>{t("Loading your farms...")}</div>
        </div>
      </div>
    );
  }

  /*
   * Farm Details
   */
  if (selectedFarm) {
    return (
      <div style={styles.page}>
        <div style={styles.container}>
          <div style={styles.topBar}>
            <button
              onClick={closeFarmDetails}
              style={styles.backButton}
            >
              ←
            </button>

            <h1 style={styles.title}>{t("Farm Details")}</h1>

            <div style={{ width: 40 }} />
          </div>

          {detailsLoading ? <div style={styles.loadingCard}>{t("Loading farm details...")}</div> : farmDetails ? <>
              {setupComplete && onboarding && <button type="button" style={styles.primarySmallButton} onClick={onFarmSaved}>{t("Continue to AgriConnect")}</button>}
              <div style={styles.farmDetailsHero}>
                <div style={styles.farmDetailsIcon}>
                  🌱
                </div>

                <div style={{ flex: 1 }}>
                  <h2 style={styles.detailsFarmName}>
                    {farmDetails.farm.farm_name}
                  </h2>

                  <p style={styles.detailsLocation}>
                    📍 {farmDetails.farm.location}
                  </p>

                  <div style={styles.areaBadgeLarge}>
                    {farmDetails.farm.total_area_acres}{t(" acres")}</div>
                </div>
              </div>

              {errorMessage && <div style={styles.errorMessage}>
                  {messageText(errorMessage)}
                </div>}

              {message && <div style={styles.message}>
                  {messageText(message)}
                </div>}

              {/*
               * Add Plot Form
               */}
              {showAddPlot ? <form onSubmit={savePlot}>
                  <div style={styles.card}>
                    <div style={styles.sectionHeader}>
                      <div>
                        <h2 style={styles.sectionTitle}>{t("Add Plot")}</h2>

                        <p
                          style={
                            styles.sectionDescription
                          }
                        >{t("Add a manageable area within this farm.")}</p>
                      </div>
                    </div>

                    <label style={styles.label}>{t("Plot name *")}</label>

                    <input
                      type="text"
                      value={plot.plotName}
                      onChange={(e) =>
                        setPlot({
                          ...plot,
                          plotName: e.target.value,
                        })
                      }
                      placeholder={t("Example: Plot 1")}
                      style={styles.input}
                    />

                    <label style={styles.label}>{t("Area (acres)")}</label>

                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={plot.areaAcres}
                      onChange={(e) =>
                        setPlot({
                          ...plot,
                          areaAcres: e.target.value,
                        })
                      }
                      placeholder={t("Example: 2")}
                      style={styles.input}
                    />

                    <label style={styles.label}>{t("Soil type")}</label>

                    <input
                      type="text"
                      value={plot.soilType}
                      onChange={(e) =>
                        setPlot({
                          ...plot,
                          soilType: e.target.value,
                        })
                      }
                      placeholder={t("Example: Red Soil")}
                      style={styles.input}
                    />

                    <label style={styles.label}>{t("Irrigation type")}</label>

                    <input
                      type="text"
                      value={plot.irrigationType}
                      onChange={(e) =>
                        setPlot({
                          ...plot,
                          irrigationType: e.target.value,
                        })
                      }
                      placeholder={t("Example: Borewell")}
                      style={styles.input}
                    />

                    <button
                      type="submit"
                      disabled={savingPlot}
                      style={{
                        ...styles.primaryButton,
                        opacity: savingPlot ? 0.7 : 1,
                      }}
                    >
                      {savingPlot ? t("Saving...") : t("Save Plot")}
                    </button>

                    <button
                      type="button"
                      onClick={closeAddPlot}
                      disabled={savingPlot}
                      style={styles.secondaryButton}
                    >{t("Cancel")}</button>
                  </div>
                </form> : showAddCrop ? <form onSubmit={saveCrop}>
                  <div style={styles.card}>
                    <div style={styles.sectionHeader}>
                      <div>
                        <h2 style={styles.sectionTitle}>{t("Add Crop")}</h2>

                        <p
                          style={
                            styles.sectionDescription
                          }
                        >{t("Add a crop to one of the plots in this farm.")}</p>
                      </div>
                    </div>

                    <label style={styles.label}>{t("Plot *")}</label>

                    <select
                      value={crop.plotId}
                      onChange={(e) =>
                        setCrop({
                          ...crop,
                          plotId: e.target.value,
                        })
                      }
                      style={styles.input}
                    >
                      <option value="">{t("Select a plot")}</option>

                      {farmDetails.plots.map(
                        (plotItem) => (
                          <option
                            key={plotItem.plot_id}
                            value={plotItem.plot_id}
                          >
                            {plotItem.plot_name}
                          </option>
                        )
                      )}
                    </select>

                    <label style={styles.label}>{t("Crop *")}</label>

                    {cropCatalogueLoading ? (
                      <div style={styles.selectLoading}>{t("Loading crops...")}</div>
                    ) : (
                      <select
                        value={crop.cropId}
                        onChange={(e) =>
                          setCrop({
                            ...crop,
                            cropId: e.target.value,
                          })
                        }
                        style={styles.input}
                      >
                        <option value="">{t("Select a crop")}</option>

                        {cropCatalogue.map(
                          (cropItem) => (
                            <option
                              key={cropItem.crop_id}
                              value={cropItem.crop_id}
                            >
                              {cropItem.crop_name}
                            </option>
                          )
                        )}
                      </select>
                    )}

                    <label style={styles.label}>{t("Season")}</label>

                    <input
                      type="text"
                      value={crop.season}
                      onChange={(e) =>
                        setCrop({
                          ...crop,
                          season: e.target.value,
                        })
                      }
                      placeholder={t("Example: Kharif 2026")}
                      style={styles.input}
                    />

                    <label style={styles.label}>{t("Planted on")}</label>

                    <input
                      type="date"
                      value={crop.plantedOn}
                      onChange={(e) =>
                        setCrop({
                          ...crop,
                          plantedOn: e.target.value,
                        })
                      }
                      style={styles.input}
                    />

                    <label style={styles.label}>{t("Expected harvest")}</label>

                    <input
                      type="date"
                      value={crop.expectedHarvestOn}
                      onChange={(e) =>
                        setCrop({
                          ...crop,
                          expectedHarvestOn:
                            e.target.value,
                        })
                      }
                      style={styles.input}
                    />

                    <button
                      type="submit"
                      disabled={
                        savingCrop ||
                        cropCatalogueLoading ||
                        farmDetails.plots.length === 0
                      }
                      style={{
                        ...styles.primaryButton,
                        opacity:
                          savingCrop ||
                          cropCatalogueLoading ||
                          farmDetails.plots.length === 0
                            ? 0.7
                            : 1,
                      }}
                    >
                      {savingCrop ? t("Saving...") : t("Save Crop")}
                    </button>

                    <button
                      type="button"
                      onClick={closeAddCrop}
                      disabled={savingCrop}
                      style={styles.secondaryButton}
                    >{t("Cancel")}</button>
                  </div>
                </form> : <>
                  {/*
                   * Plots
                   */}
                  <div style={styles.card}>
                    <div style={styles.sectionHeader}>
                      <div>
                        <h2 style={styles.sectionTitle}>{t("Plots")}</h2>

                        <p
                          style={
                            styles.sectionDescription
                          }
                        >{t("Manage the different plots within this farm.")}</p>
                      </div>

                      <span style={styles.countBadge}>
                        {farmDetails.plots.length}
                      </span>
                    </div>

                    {farmDetails.plots.length === 0 ? (
                      <div style={styles.emptySection}>
                        <div
                          style={
                            styles.emptySectionIcon
                          }
                        >
                          🧑‍🌾
                        </div>

                        <h3
                          style={
                            styles.emptySectionTitle
                          }
                        >{t("No plots added yet")}</h3>

                        <p
                          style={
                            styles.emptySectionText
                          }
                        >{t("Add plots to organize different areas of this farm.")}</p>

                        <button
                          type="button"
                          style={
                            styles.primarySmallButton
                          }
                          onClick={openAddPlot}
                        >{t("+ Add Plot")}</button>
                      </div>
                    ) : (
                      <>
                        {farmDetails.plots.map(
                          (plotItem) => (
                            <div
                              key={plotItem.plot_id}
                              id={`farm-plot-${plotItem.plot_id}`}
                              className={savedPlotId === plotItem.plot_id ? "cm-saved" : ""}
                              style={styles.plotCard}
                            >
                              <div
                                style={{ flex: 1 }}
                              >
                                <h3
                                  style={
                                    styles.plotName
                                  }
                                >
                                  {plotItem.plot_name}
                                </h3>
                                <button type="button" style={styles.primarySmallButton} onClick={() => setBlockPlotId(plotItem.plot_id)}>{t("Blocks")}</button>
                                {onStartCrop && <button type="button" style={styles.primarySmallButton} onClick={() => onStartCrop({ farm_id: selectedFarm.farm_id, plot_id: plotItem.plot_id })}>{t("Start Crop")}</button>}

                                {plotItem.area_acres !==
                                  null && (
                                  <p
                                    style={
                                      styles.plotInfo
                                    }
                                  >{t("Area:")}{" "}
                                    {
                                      plotItem.area_acres
                                    }{" "}{t("acres")}</p>
                                )}

                                {plotItem.soil_type && (
                                  <p
                                    style={
                                      styles.plotInfo
                                    }
                                  >{t("Soil:")}{" "}
                                    {
                                      plotItem.soil_type
                                    }
                                  </p>
                                )}

                                {plotItem.irrigation_type && (
                                  <p
                                    style={
                                      styles.plotInfo
                                    }
                                  >{t("Irrigation:")}{" "}
                                    {
                                      plotItem.irrigation_type
                                    }
                                  </p>
                                )}
                              </div>
                            </div>
                          )
                        )}

                        <button
                          type="button"
                          style={styles.addPlotButton}
                          onClick={openAddPlot}
                        >{t("+ Add Plot")}</button>
                      </>
                    )}
                  </div>

                  {/*
                   * Crops
                   */}
                  {farmDetails.plots.some((p) => p.plot_id === blockPlotId) && <section className="cm-page cm-embedded">
                    <div className="cm-row"><h2>{farmDetails.plots.find((p) => p.plot_id === blockPlotId).plot_name}{t(" · Blocks")}</h2><button type="button" onClick={() => setBlockPlotId(null)}>{t("Close blocks")}</button></div>
                    <BlockManager key={blockPlotId} api={cropApi} farmId={selectedFarm.farm_id} plotId={blockPlotId} plots={farmDetails.plots.filter((p) => p.plot_id === blockPlotId)} />
                  </section>}
                  <details className="cm-page cm-embedded" onToggle={(e) => setShowFarmRecords(e.currentTarget.open)}><summary>{t("Farm-wide work & expense records")}</summary>
                    {showFarmRecords && <FarmWorkspace key={selectedFarm.farm_id} api={cropApi} farms={[farmDetails.farm]} initialFarmId={selectedFarm.farm_id} showBlocks={false} />}
                  </details>
                  <div style={styles.card}>
                    <div style={styles.sectionHeader}>
                      <div>
                        <h2 style={styles.sectionTitle}>{t("Crops")}</h2>

                        <p
                          style={
                            styles.sectionDescription
                          }
                        >{t("Manage crops grown on your farm plots.")}</p>
                      </div>

                      <span style={styles.countBadge}>
                        {farmDetails.crops.length}
                      </span>
                    </div>

                    {farmDetails.crops.length === 0 ? (
                      <div style={styles.emptySection}>
                        <div
                          style={
                            styles.emptySectionIcon
                          }
                        >
                          🌾
                        </div>

                        <h3
                          style={
                            styles.emptySectionTitle
                          }
                        >{t("No crops added yet")}</h3>

                        <p
                          style={
                            styles.emptySectionText
                          }
                        >{t("Add a crop and associate it with one of your plots.")}</p>

                        {farmDetails.plots.length >
                          0 && (
                          <button
                            type="button"
                            style={
                              styles.primarySmallButton
                            }
                            onClick={openAddCrop}
                          >{t("+ Add Crop")}</button>
                        )}
                      </div>
                    ) : (
                      <>
                        {farmDetails.crops.map(
                          (cropItem) => (
                            <div
                              key={
                                cropItem.farm_crop_id
                              }
                              style={styles.cropCard}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent:
                                    "space-between",
                                  alignItems:
                                    "flex-start",
                                  gap: "12px",
                                }}
                              >
                                <div>
                                  <h3
                                    style={
                                      styles.cropName
                                    }
                                  >
                                    {
                                      cropItem.crop_name
                                    }
                                  </h3>

                                  {cropItem.scientific_name && (
                                    <p
                                      style={
                                        styles.cropScientificName
                                      }
                                    >
                                      {
                                        cropItem.scientific_name
                                      }
                                    </p>
                                  )}
                                </div>

                                <span
                                  style={
                                    styles.statusBadge
                                  }
                                >
                                  {
                                    cropStatusLabel(cropItem)
                                  }
                                </span>
                              </div>

                              {cropItem.plot_id && (
                                <p
                                  style={
                                    styles.cropInfo
                                  }
                                >{t("Plot:")}{" "}
                                  {cropItem.plot_name || t("Plot {{v0}}", { v0: cropItem.plot_id })}
                                </p>
                              )}

                              {cropItem.season && (
                                <p
                                  style={
                                    styles.cropInfo
                                  }
                                >{t("Season:")}{" "}
                                  {cropItem.season}
                                </p>
                              )}

                              {cropItem.planted_on && (
                                <p
                                  style={
                                    styles.cropInfo
                                  }
                                >{t("Planted:")}{" "}
                                  {
                                    cropItem.planted_on
                                  }
                                </p>
                              )}

                              {cropItem.expected_harvest_on && (
                                <p
                                  style={
                                    styles.cropInfo
                                  }
                                >{t("Expected harvest:")}{" "}
                                  {
                                    cropItem.expected_harvest_on
                                  }
                                </p>
                              )}
                            </div>
                          )
                        )}

                        <button
                          type="button"
                          style={
                            styles.addPlotButton
                          }
                          onClick={openAddCrop}
                        >{t("+ Add Crop")}</button>
                      </>
                    )}
                  </div>
                </>}
            </> : null}
        </div>
      </div>
    );
  }

  /*
   * Add Farm
   */
  if (showAddFarm) {
    return (
      <div style={styles.page}>
        <div style={styles.container}>
          <div style={styles.topBar}>
            <button
              onClick={onboarding ? onBack : closeAddFarm}
              style={styles.backButton}
            >
              ←
            </button>

            <h1 style={styles.title}>{addressOnly ? t("Add Service Address") : t("Add Farm")}</h1>

            <div style={{ width: 40 }} />
          </div>

          <form onSubmit={saveSetup}>
            {!farmCreated && <div style={styles.card}>
              <h2 style={styles.sectionTitle}>{t("Farm details")}</h2>

              <label style={styles.label}>{t("Farm name *")}</label>

              <input
                type="text"
                value={farm.farmName}
                onChange={(e) =>
                  setFarm({
                    ...farm,
                    farmName: e.target.value,
                  })
                }
                placeholder={t("Example: BJR farms")}
                style={styles.input}
              />

              <label style={styles.label}>{t("Village / Location *")}</label>

              <input
                type="text"
                value={farm.location}
                onChange={(e) =>
                  setFarm({
                    ...farm,
                    location: e.target.value,
                  })
                }
                placeholder={t("Example: Kothapalli")}
                style={styles.input}
              />

              <label style={styles.label}>{t("Total area (acres) *")}</label>

              <input
                type="number"
                min="0.01"
                step="0.01"
                value={farm.totalAreaAcres}
                onChange={(e) =>
                  setFarm({
                    ...farm,
                    totalAreaAcres: e.target.value,
                  })
                }
                placeholder={t("Example: 5")}
                style={styles.input}
              />
            </div>}

            <div style={styles.card}>
              <h2 style={styles.sectionTitle}>{t("Address")}{" "}
                <span style={styles.optional}>
                  {onboarding ? t("(required for bookings)") : t("(optional)")}
                </span>
              </h2>

              <label style={styles.label}>{t("Address label")}</label>

              <input
                type="text"
                value={address.label}
                onChange={(e) =>
                  setAddress({
                    ...address,
                    label: e.target.value,
                  })
                }
                placeholder={t("Example: Farm Address")}
                style={styles.input}
              />

              <label style={styles.label}>{t("Address line")}</label>

              <input
                type="text"
                value={address.addressLine1}
                onChange={(e) =>
                  setAddress({
                    ...address,
                    addressLine1: e.target.value,
                  })
                }
                placeholder={t("House / street / landmark")}
                style={styles.input}
              />

              <label style={styles.label}>{t("Village / City")}</label>

              <input
                type="text"
                value={address.villageOrCity}
                onChange={(e) =>
                  setAddress({
                    ...address,
                    villageOrCity: e.target.value,
                  })
                }
                placeholder={t("Village or city")}
                style={styles.input}
              />

              <label style={styles.label}>{t("District")}</label>

              <input
                type="text"
                value={address.district}
                onChange={(e) =>
                  setAddress({
                    ...address,
                    district: e.target.value,
                  })
                }
                placeholder={t("District")}
                style={styles.input}
              />

              <label style={styles.label}>{t("State")}</label>

              <input
                type="text"
                value={address.state}
                onChange={(e) =>
                  setAddress({
                    ...address,
                    state: e.target.value,
                  })
                }
                placeholder={t("State")}
                style={styles.input}
              />

              <label style={styles.label}>{t("Postal code")}</label>

              <input
                type="text"
                value={address.postalCode}
                onChange={(e) =>
                  setAddress({
                    ...address,
                    postalCode: e.target.value,
                  })
                }
                placeholder={t("Postal code")}
                style={styles.input}
              />
            </div>

            {errorMessage && <div style={styles.errorMessage}>
                {messageText(errorMessage)}
              </div>}

            <button
              type="submit"
              disabled={saving}
              style={{
                ...styles.primaryButton,
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? t("Saving...") : t("Save Farm")}
            </button>

            <button
              type="button"
              onClick={onboarding ? onBack : closeAddFarm}
              disabled={saving}
              style={styles.secondaryButton}
            >{t("Cancel")}</button>
          </form>
        </div>
      </div>
    );
  }

  /*
   * My Farms
   */
  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <div style={styles.topBar}>
          <button
            onClick={onBack}
            style={styles.backButton}
          >
            ←
          </button>

          <h1 style={styles.title}>{t("My Farms")}</h1>

          <div style={{ width: 40 }} />
        </div>

        <div style={styles.intro}>
          <h2 style={styles.introTitle}>{t("Your farms")}</h2>

          <p style={styles.introText}>{t("Manage your farms and organize your agricultural activities.")}</p>
        </div>

        {errorMessage && <div style={styles.errorMessage}>
            {messageText(errorMessage)}
          </div>}

        {message && <div style={styles.message}>
            {messageText(message)}
          </div>}

        {farms.length === 0 ? <div style={styles.emptyCard}>
            <div style={styles.emptyIcon}>🌱</div>

            <h2 style={styles.emptyTitle}>{t("No farms added yet")}</h2>

            <p style={styles.emptyText}>{t("Add your first farm to start organizing your plots, crops and future farm activities.")}</p>
          </div> : <div>
            {farms.map((item) => (
              <div
                key={item.farm_id}
                style={styles.farmCard}
              >
                <div style={styles.farmHeader}>
                  <div style={{ flex: 1 }}>
                    <h2 style={styles.farmName}>
                      {item.farm_name}
                    </h2>

                    <p style={styles.location}>
                      📍 {item.location}
                    </p>
                  </div>

                  <div style={styles.areaBadge}>
                    {item.total_area_acres}{t(" acres")}</div>
                </div>

                <div style={styles.farmFooter}>
                  <span style={styles.farmHint}>{t("Open farm details")}</span>

                  <button
                    type="button"
                    style={styles.viewButton}
                    onClick={() =>
                      openFarmDetails(item)
                    }
                  >{t("View →")}</button>
                </div>
              </div>
            ))}
          </div>}

        <button
          type="button"
          onClick={openAddFarm}
          style={styles.addFarmButton}
        >{t("+ Add Farm")}</button>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#f6f8f5",
    padding: "16px",
    boxSizing: "border-box",
  },

  container: {
    width: "100%",
    maxWidth: "680px",
    margin: "0 auto",
  },

  topBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "20px",
  },

  backButton: {
    width: "40px",
    height: "40px",
    border: "none",
    borderRadius: "12px",
    background: "#ffffff",
    fontSize: "22px",
    cursor: "pointer",
    boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
  },

  title: {
    margin: 0,
    fontSize: "22px",
    fontWeight: "700",
  },

  intro: {
    marginBottom: "18px",
  },

  introTitle: {
    margin: "0 0 5px",
    fontSize: "20px",
  },

  introText: {
    margin: 0,
    color: "#667064",
    fontSize: "14px",
    lineHeight: 1.5,
  },

  loadingCard: {
    background: "#ffffff",
    borderRadius: "16px",
    padding: "24px",
    textAlign: "center",
    color: "#667064",
  },

  card: {
    background: "#ffffff",
    borderRadius: "16px",
    padding: "18px",
    marginBottom: "16px",
    boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
  },

  farmDetailsHero: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    background: "#ffffff",
    borderRadius: "16px",
    padding: "18px",
    marginBottom: "16px",
    boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
  },

  farmDetailsIcon: {
    width: "52px",
    height: "52px",
    borderRadius: "14px",
    background: "#edf5e9",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "27px",
  },

  detailsFarmName: {
    margin: "0 0 5px",
    fontSize: "20px",
  },

  detailsLocation: {
    margin: "0 0 9px",
    color: "#687065",
    fontSize: "13px",
  },

  areaBadgeLarge: {
    display: "inline-block",
    background: "#edf5e9",
    padding: "6px 9px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "600",
  },

  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "10px",
    marginBottom: "14px",
  },

  sectionTitle: {
    margin: 0,
    fontSize: "18px",
  },

  sectionDescription: {
    margin: "5px 0 0",
    color: "#747b70",
    fontSize: "13px",
    lineHeight: 1.4,
  },

  countBadge: {
    minWidth: "25px",
    height: "25px",
    padding: "0 7px",
    borderRadius: "20px",
    background: "#edf5e9",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "12px",
    fontWeight: "700",
  },

  emptySection: {
    border: "1px dashed #d6ddd3",
    borderRadius: "12px",
    padding: "20px 14px",
    textAlign: "center",
  },

  emptySectionIcon: {
    fontSize: "28px",
    marginBottom: "7px",
  },

  emptySectionTitle: {
    margin: "0 0 6px",
    fontSize: "15px",
  },

  emptySectionText: {
    margin: "0 auto 14px",
    maxWidth: "380px",
    color: "#747b70",
    fontSize: "13px",
    lineHeight: 1.5,
  },

  primarySmallButton: {
    minHeight: "44px",
    maxWidth: "100%",
    border: "none",
    borderRadius: "9px",
    padding: "10px 14px",
    background: "#2f6b2f",
    color: "#ffffff",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
  },

  addPlotButton: {
    width: "100%",
    border: "1px solid #d7ddd4",
    borderRadius: "10px",
    padding: "11px",
    background: "#ffffff",
    color: "#2f6b2f",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
    marginTop: "14px",
  },

  plotCard: {
    display: "flex",
    padding: "13px 0",
    borderTop: "1px solid #edf0eb",
  },

  plotName: {
    margin: 0,
    fontSize: "15px",
  },

  plotInfo: {
    margin: "5px 0 0",
    color: "#727a70",
    fontSize: "12px",
  },

  cropCard: {
    padding: "13px 0",
    borderTop: "1px solid #edf0eb",
  },

  cropName: {
    margin: 0,
    fontSize: "15px",
  },

  cropScientificName: {
    margin: "4px 0 0",
    color: "#7a8177",
    fontSize: "12px",
    fontStyle: "italic",
  },

  cropInfo: {
    margin: "5px 0 0",
    color: "#727a70",
    fontSize: "12px",
  },

  statusBadge: {
    background: "#edf5e9",
    color: "#315d2c",
    padding: "5px 8px",
    borderRadius: "8px",
    fontSize: "11px",
    fontWeight: "700",
    textTransform: "capitalize",
  },

  selectLoading: {
    width: "100%",
    boxSizing: "border-box",
    padding: "12px",
    border: "1px solid #d7ddd4",
    borderRadius: "10px",
    fontSize: "14px",
    color: "#747b70",
    background: "#fafbf9",
  },

  label: {
    display: "block",
    marginBottom: "6px",
    marginTop: "13px",
    fontSize: "13px",
    fontWeight: "600",
    color: "#3f463d",
  },

  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: "12px",
    border: "1px solid #d7ddd4",
    borderRadius: "10px",
    fontSize: "15px",
    outline: "none",
    background: "#ffffff",
  },

  optional: {
    fontSize: "12px",
    fontWeight: "400",
    color: "#777",
  },

  message: {
    background: "#eef6eb",
    color: "#315d2c",
    padding: "12px 14px",
    borderRadius: "10px",
    marginBottom: "14px",
    fontSize: "14px",
  },

  errorMessage: {
    background: "#fff0f0",
    color: "#9b2c2c",
    padding: "12px 14px",
    borderRadius: "10px",
    marginBottom: "14px",
    fontSize: "14px",
  },

  farmCard: {
    background: "#ffffff",
    borderRadius: "16px",
    padding: "17px",
    marginBottom: "12px",
    boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
  },

  farmHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "12px",
  },

  farmName: {
    margin: 0,
    fontSize: "18px",
  },

  location: {
    margin: "7px 0 0",
    color: "#687065",
    fontSize: "14px",
  },

  areaBadge: {
    whiteSpace: "nowrap",
    background: "#edf5e9",
    padding: "7px 9px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "600",
  },

  farmFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "10px",
    marginTop: "16px",
    paddingTop: "12px",
    borderTop: "1px solid #edf0eb",
  },

  farmHint: {
    color: "#7a8177",
    fontSize: "12px",
  },

  viewButton: {
    border: "none",
    background: "transparent",
    fontWeight: "700",
    cursor: "pointer",
    fontSize: "13px",
  },

  emptyCard: {
    background: "#ffffff",
    borderRadius: "16px",
    padding: "30px 20px",
    textAlign: "center",
    boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
  },

  emptyIcon: {
    fontSize: "38px",
    marginBottom: "10px",
  },

  emptyTitle: {
    margin: "0 0 8px",
    fontSize: "18px",
  },

  emptyText: {
    margin: "0 auto",
    maxWidth: "440px",
    color: "#6d756b",
    fontSize: "14px",
    lineHeight: 1.5,
  },

  primaryButton: {
    width: "100%",
    border: "none",
    borderRadius: "12px",
    padding: "14px",
    background: "#2f6b2f",
    color: "#ffffff",
    fontSize: "15px",
    fontWeight: "700",
    cursor: "pointer",
    marginBottom: "10px",
    marginTop: "16px",
  },

  secondaryButton: {
    width: "100%",
    border: "1px solid #d7ddd4",
    borderRadius: "12px",
    padding: "13px",
    background: "#ffffff",
    fontSize: "15px",
    fontWeight: "600",
    cursor: "pointer",
  },

  addFarmButton: {
    width: "100%",
    border: "none",
    borderRadius: "12px",
    padding: "14px",
    background: "#2f6b2f",
    color: "#ffffff",
    fontSize: "15px",
    fontWeight: "700",
    cursor: "pointer",
    marginTop: "16px",
  },
};

export default FarmSetup;
