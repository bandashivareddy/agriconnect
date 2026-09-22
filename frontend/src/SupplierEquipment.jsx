import { useEffect, useState } from "react";
import "./SupplierEquipment.css";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function SupplierEquipment({ token, onBack }) {
  const [categories, setCategories] = useState([]);
  const [equipment, setEquipment] = useState([]);
  const [services, setServices] = useState([]);

  const [message, setMessage] = useState("");
  const [showAddEquipment, setShowAddEquipment] = useState(false);

  const [loadingServices, setLoadingServices] = useState(false);
  const [savingServices, setSavingServices] = useState(false);

  const [selectedEquipmentId, setSelectedEquipmentId] = useState(null);
  const [selectedServiceIds, setSelectedServiceIds] = useState([]);

  const [form, setForm] = useState({
    categoryId: "",
    equipmentName: "",
    brand: "",
    model: "",
    description: "",
    dailyRate: "",
    securityDeposit: "",
    quantityAvailable: "1",
  });

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  // =========================================================
  // LOAD EQUIPMENT DATA
  // =========================================================

  useEffect(() => {
    async function loadEquipment() {
      try {
        const [categoryResponse, equipmentResponse] =
          await Promise.all([
            fetch(`${API_URL}/equipment-categories`),
            fetch(`${API_URL}/supplier/equipment`, {
              headers,
            }),
          ]);

        const [categoryData, equipmentData] =
          await Promise.all([
            categoryResponse.json(),
            equipmentResponse.json(),
          ]);

        if (
          !categoryResponse.ok ||
          !Array.isArray(categoryData)
        ) {
          throw new Error(
            "Could not load equipment categories."
          );
        }

        if (
          !equipmentResponse.ok ||
          !Array.isArray(equipmentData)
        ) {
          throw new Error(
            "Could not load supplier equipment."
          );
        }

        setCategories(categoryData);
        setEquipment(equipmentData);

        setForm((current) => ({
          ...current,
          categoryId: String(
            categoryData[0]?.equipment_category_id || ""
          ),
        }));
      } catch (error) {
        console.error(
          "Equipment load error:",
          error
        );

        setMessage(
          error.message ||
            "Could not load equipment data."
        );
      }
    }

    loadEquipment();
  }, [token]);

  // =========================================================
  // LOAD SUPPLIER SERVICES
  // =========================================================

  useEffect(() => {
    async function loadServices() {
      try {
        const response = await fetch(
          `${API_URL}/supplier/services`,
          { headers }
        );

        const data = await response.json();

        if (!response.ok || !Array.isArray(data)) {
          throw new Error(
            data.detail ||
              "Could not load supplier services."
          );
        }

        setServices(data);
      } catch (error) {
        console.error(
          "Supplier services load error:",
          error
        );

        setMessage(
          error.message ||
            "Could not load supplier services."
        );
      }
    }

    loadServices();
  }, [token]);

  // =========================================================
  // FORM FIELD UPDATE
  // =========================================================

  function updateField(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  // =========================================================
  // ADD EQUIPMENT
  // =========================================================

  async function addEquipment(event) {
    event.preventDefault();
    setMessage("");

    try {
      const response = await fetch(
        `${API_URL}/supplier/equipment`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            equipment_category_id:
              Number(form.categoryId),

            equipment_name:
              form.equipmentName,

            brand:
              form.brand || null,

            model:
              form.model || null,

            description:
              form.description || null,

            daily_rate:
              form.dailyRate
                ? Number(form.dailyRate)
                : null,

            security_deposit:
              form.securityDeposit
                ? Number(form.securityDeposit)
                : 0,

            quantity_available:
              Number(form.quantityAvailable),
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(
          result.detail ||
            "Equipment could not be added."
        );
        return;
      }

      setEquipment((current) => [
        result,
        ...current,
      ]);

      setMessage(
        `${result.equipment_name} was added successfully.`
      );

      setShowAddEquipment(false);

      setForm((current) => ({
        ...current,
        equipmentName: "",
        brand: "",
        model: "",
        description: "",
        dailyRate: "",
        securityDeposit: "",
        quantityAvailable: "1",
      }));
    } catch (error) {
      console.error(
        "Add equipment error:",
        error
      );

      setMessage(
        error.message ||
          "Equipment could not be added."
      );
    }
  }

  // =========================================================
  // OPEN SERVICE MANAGER
  // =========================================================

  async function openServiceManager(equipmentId) {
    setMessage("");
    setSelectedEquipmentId(equipmentId);
    setSelectedServiceIds([]);
    setLoadingServices(true);

    try {
      const response = await fetch(
        `${API_URL}/supplier/equipment/${equipmentId}/services`,
        {
          headers,
        }
      );

      const linkedServices = await response.json();

      if (!response.ok || !Array.isArray(linkedServices)) {
        throw new Error(
          linkedServices.detail ||
            "Could not load linked services."
        );
      }

      setSelectedServiceIds(
        linkedServices.map(
          (service) =>
            service.supplier_service_id
        )
      );
    } catch (error) {
      console.error(
        "Load equipment services error:",
        error
      );

      setMessage(
        error.message ||
          "Could not load linked services."
      );

      setSelectedEquipmentId(null);
    } finally {
      setLoadingServices(false);
    }
  }

  // =========================================================
  // CLOSE SERVICE MANAGER
  // =========================================================

  function closeServiceManager() {
    if (savingServices) {
      return;
    }

    setSelectedEquipmentId(null);
    setSelectedServiceIds([]);
  }

  // =========================================================
  // TOGGLE SERVICE
  // =========================================================

  function toggleService(serviceId) {
    setSelectedServiceIds((current) =>
      current.includes(serviceId)
        ? current.filter(
            (id) => id !== serviceId
          )
        : [...current, serviceId]
    );
  }

  // =========================================================
  // SAVE EQUIPMENT SERVICES
  // =========================================================

  async function saveEquipmentServices() {
    if (!selectedEquipmentId) {
      return;
    }

    setSavingServices(true);
    setMessage("");

    try {
      const response = await fetch(
        `${API_URL}/supplier/equipment/${selectedEquipmentId}/services`,
        {
          method: "PUT",
          headers,
          body: JSON.stringify({
            service_ids: selectedServiceIds,
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail ||
            "Equipment services could not be updated."
        );
      }

      setMessage(
        "Equipment services updated successfully."
      );

      setSelectedEquipmentId(null);
      setSelectedServiceIds([]);
    } catch (error) {
      console.error(
        "Save equipment services error:",
        error
      );

      setMessage(
        error.message ||
          "Equipment services could not be updated."
      );
    } finally {
      setSavingServices(false);
    }
  }

  // =========================================================
  // FORMAT PRICE
  // =========================================================

  function formatDailyRate(item) {
    if (!item.daily_rate) {
      return "Rate on request";
    }

    return `₹${Number(
      item.daily_rate
    ).toLocaleString("en-IN")} / day`;
  }

  // =========================================================
  // PAGE
  // =========================================================

  return (
    <main className="equipment-page">

      <section className="equipment-content">

        <div className="equipment-topbar">
          <button aria-label="Back to marketplace" className="equipment-back-button" onClick={onBack}>←</button>
          <h1>My Equipment</h1>
          <div aria-hidden="true" />
        </div>

        <div className="equipment-intro">
          <p>Manage machinery and equipment used for your services.</p>
        </div>

        <section className="equipment-section equipment-collection">

          {equipment.length === 0 ? (
            <p>No equipment listed yet.</p>
          ) : (
            <div className="equipment-list">
              {equipment.map((item) => (
                <article className="equipment-card" key={item.equipment_id}>
                  <div className="equipment-card-main">
                    <span>{item.category_name || "Equipment"}</span>
                    <h3>{item.equipment_name}</h3>
                    <p>{[item.brand, item.model].filter(Boolean).join(" · ") || "Brand/model not specified"}</p>
                    <p>{formatDailyRate(item)}</p>
                    <p>Available: {item.quantity_available}</p>
                    {item.description && <p>{item.description}</p>}
                  </div>
                  <button className="secondary-action" type="button" onClick={() => openServiceManager(item.equipment_id)}>Manage →</button>
                </article>
              ))}
            </div>
          )}

          <button className="primary-button equipment-add-button" type="button" onClick={() => setShowAddEquipment((current) => !current)}>
            {showAddEquipment ? "Close add equipment" : "+ Add Equipment"}
          </button>

          {showAddEquipment && (
          <section className="equipment-section equipment-add-section">

          <h2>
            Add equipment
          </h2>

          <form
            className="equipment-form"
            onSubmit={addEquipment}
          >

            <label>
              Equipment category

              <select
                name="categoryId"
                value={form.categoryId}
                onChange={updateField}
                required
              >
                {categories.map((category) => (
                  <option
                    key={
                      category.equipment_category_id
                    }
                    value={
                      category.equipment_category_id
                    }
                  >
                    {category.category_name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Equipment name

              <input
                name="equipmentName"
                value={form.equipmentName}
                onChange={updateField}
                placeholder="Example: Mahindra 575 DI Tractor"
                required
              />
            </label>

            <label>
              Brand

              <input
                name="brand"
                value={form.brand}
                onChange={updateField}
              />
            </label>

            <label>
              Model

              <input
                name="model"
                value={form.model}
                onChange={updateField}
              />
            </label>

            <label>
              Daily rental rate (₹)

              <input
                name="dailyRate"
                type="number"
                min="0"
                value={form.dailyRate}
                onChange={updateField}
              />
            </label>

            <label>
              Security deposit (₹)

              <input
                name="securityDeposit"
                type="number"
                min="0"
                value={form.securityDeposit}
                onChange={updateField}
              />
            </label>

            <label>
              Quantity available

              <input
                name="quantityAvailable"
                type="number"
                min="1"
                value={form.quantityAvailable}
                onChange={updateField}
                required
              />
            </label>

            <label className="equipment-full-width">
              Description

              <textarea
                name="description"
                rows="3"
                value={form.description}
                onChange={updateField}
                placeholder="Describe the equipment and what it can be used for."
              />
            </label>

            <button
              className="primary-button equipment-full-width"
              type="submit"
            >
              Add equipment
            </button>

          </form>

          {message && (
            <p className="equipment-message">
              {message}
            </p>
          )}
          </section>
          )}

        </section>

        {/* =====================================================
            SERVICE MANAGER
            ===================================================== */}

        {selectedEquipmentId && (

          <section className="equipment-section equipment-service-manager">

            <div className="equipment-service-manager-header">

              <div>

                <p className="eyebrow">
                  Equipment setup
                </p>

                <h2>
                  Services supported
                </h2>

                <p>
                  Select all services that this
                  equipment can be used for.
                </p>

              </div>

              <button
                type="button"
                className="secondary-action"
                onClick={closeServiceManager}
                disabled={savingServices}
              >
                Close
              </button>

            </div>

            {loadingServices ? (

              <p>
                Loading linked services...
              </p>

            ) : services.length === 0 ? (

              <div className="supplier-empty-state">
                <strong>
                  No services available.
                </strong>

                <p>
                  Add a service from the Supplier
                  Dashboard first.
                </p>
              </div>

            ) : (

              <div className="equipment-service-options">

                {services.map((service) => (

                  <label
                    className="equipment-service-option"
                    key={
                      service.supplier_service_id
                    }
                  >

                    <input
                      type="checkbox"
                      checked={selectedServiceIds.includes(
                        service.supplier_service_id
                      )}
                      onChange={() =>
                        toggleService(
                          service.supplier_service_id
                        )
                      }
                    />

                    <span>

                      <strong>
                        {service.service_name}
                      </strong>

                      <small>
                        {service.parent_category_name ||
                          service.category_name ||
                          "Agricultural service"}
                      </small>

                    </span>

                  </label>

                ))}

              </div>

            )}

            {!loadingServices &&
              services.length > 0 && (

                <button
                  type="button"
                  className="primary-button"
                  onClick={saveEquipmentServices}
                  disabled={savingServices}
                >
                  {savingServices
                    ? "Saving..."
                    : "Save services"}
                </button>

              )}

          </section>

        )}

      </section>

    </main>
  );
}

export default SupplierEquipment;
