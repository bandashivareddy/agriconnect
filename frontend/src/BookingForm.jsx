import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useRef, useState } from "react";
import "./BookingForm.css";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function BookingForm({ service, onClose, onBookingCreated, token, cropContext }) {
  useTranslation();
  const [cropRequestKey] = useState(() => crypto.randomUUID());
  const contextFarmId = cropContext?.farm_id;
  const [farms, setFarms] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [availableSlots, setAvailableSlots] = useState([]);

  const [form, setForm] = useState({
    farmId: String(contextFarmId || ""),
    addressId: "",
    date: "",
    slotIds: [],
    quantity: "1",
    notes: "",
  });

  const [notice, setNotice] = useState("");
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const bookingRequestInFlight = useRef(false);

  const [supplierDetails, setSupplierDetails] = useState({
    supplierName: service?.supplier_name || "Service Provider",
    serviceName: service?.service_name || "",
    basePrice: service?.base_price || 0,
    pricingUnit: service?.pricing_unit || "unit",
    averageRating: service?.average_rating || 0,
  });

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  function getTodayString() {
    const today = new Date();

    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
  }

  useEffect(() => {
    const bookingSection = document.getElementById("booking");

    if (bookingSection) {
      bookingSection.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, []);

  useEffect(() => {
    async function loadBookingDetails() {
      if (!token) {
        setNotice("Please sign in before creating a booking.");
        setLoadingDetails(false);
        return;
      }

      try {
        const [farmsResponse, addressesResponse] =
          await Promise.all([
            fetch(`${API_URL}/my/farms`, {
              headers,
            }),
            fetch(`${API_URL}/my/addresses`, {
              headers,
            }),
          ]);

        if (
          farmsResponse.status === 401 ||
          addressesResponse.status === 401
        ) {
          setNotice(
            "Your session has expired. Please sign out and sign in again."
          );

          setFarms([]);
          setAddresses([]);

          return;
        }

        const farmData = await farmsResponse.json();
        const addressData = await addressesResponse.json();

        if (!farmsResponse.ok) {
          throw new Error(
            farmData.detail || "Could not load your farms."
          );
        }

        if (!addressesResponse.ok) {
          throw new Error(
            addressData.detail ||
              "Could not load your addresses."
          );
        }

        if (!Array.isArray(farmData)) {
          throw new Error("Could not load your farms.");
        }

        if (!Array.isArray(addressData)) {
          throw new Error("Could not load your addresses.");
        }

        setFarms(farmData);
        setAddresses(addressData);

        setForm((current) => ({
          ...current,
          farmId: String(
            contextFarmId || farmData[0]?.farm_id || ""
          ),
          addressId: String(
            addressData[0]?.address_id || ""
          ),
        }));

        if (farmData.length === 0) {
          setNotice(
            "Please add a farm in Farm setup before booking."
          );
        } else if (addressData.length === 0) {
          setNotice(
            "Please add a service address before booking."
          );
        }
      } catch (error) {
        console.error(error);

        setNotice(
          error.message ||
            "Could not load booking details."
        );

        setFarms([]);
        setAddresses([]);
      } finally {
        setLoadingDetails(false);
      }
    }

    loadBookingDetails();
  }, [token, contextFarmId]);

  useEffect(() => {
    async function loadAvailableSlots() {
      if (
        !form.date ||
        !service?.supplier_service_id
      ) {
        setAvailableSlots([]);
        return;
      }

      setLoadingSlots(true);
      setNotice("");

      try {
        const response = await fetch(
          `${API_URL}/supplier-services/${service.supplier_service_id}/availability?date=${form.date}`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Could not load available time slots."
          );
        }

        if (!Array.isArray(data)) {
          throw new Error(
            "Could not load available time slots."
          );
        }

        /*
         * The backend already removes full slots.
         * This additional check prevents a past slot from
         * appearing if today's date is selected.
         */
        const now = new Date();

        const futureSlots = data
          .filter((slot) => {
            const slotStart = new Date(slot.starts_at);
            return slotStart > now;
          })
          .sort(
            (a, b) =>
              new Date(a.starts_at) -
              new Date(b.starts_at)
          );

        setAvailableSlots(futureSlots);

        if (data.length > 0) {
          const firstSlot = data[0];

          setSupplierDetails({
            supplierName:
              firstSlot.supplier_name ||
              service.supplier_name ||
              "Service Provider",

            serviceName:
              firstSlot.service_name ||
              service.service_name ||
              "",

            basePrice:
              firstSlot.base_price ??
              service.base_price ??
              0,

            pricingUnit:
              firstSlot.pricing_unit ||
              service.pricing_unit ||
              "unit",

            averageRating:
              firstSlot.average_rating ??
              service.average_rating ??
              0,
          });
        }

        setForm((current) => ({
          ...current,
          slotIds: [],
        }));

        if (futureSlots.length === 0) {
          setNotice(
            "No available time slots for this date."
          );
        }
      } catch (error) {
        console.error(error);

        setAvailableSlots([]);

        setNotice(
          error.message ||
            "Could not load available time slots."
        );
      } finally {
        setLoadingSlots(false);
      }
    }

    loadAvailableSlots();
  }, [
    form.date,
    service?.supplier_service_id,
  ]);

  function updateField(event) {
    const { name, value } = event.target;

    if (name === "date") {
      setForm((current) => ({
        ...current,
        date: value,
        slotIds: [],
      }));

      setAvailableSlots([]);
      setNotice("");

      return;
    }

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  /*
   * Returns selected slots in chronological order.
   */
  function getSelectedSlots() {
    return availableSlots
      .filter((slot) =>
        form.slotIds.includes(
          String(slot.availability_slot_id)
        )
      )
      .sort(
        (a, b) =>
          new Date(a.starts_at) -
          new Date(b.starts_at)
      );
  }

  /*
   * Check whether two slots touch each other.
   *
   * Example:
   *
   * 08:00-09:00
   * 09:00-10:00
   *
   * These are consecutive.
   */
  function areConsecutive(slotA, slotB) {
    const endA = new Date(slotA.ends_at).getTime();
    const startB = new Date(slotB.starts_at).getTime();

    return endA === startB;
  }

  /*
   * Select or deselect an hourly slot.
   *
   * Only consecutive slots can be selected.
   */
  function selectSlot(slot) {
    const slotId = String(
      slot.availability_slot_id
    );

    const selectedSlots = getSelectedSlots();

    const alreadySelected =
      form.slotIds.includes(slotId);

    /*
     * ---------------------------------------------------------
     * Deselect
     * ---------------------------------------------------------
     */
    if (alreadySelected) {
      /*
       * If only one slot is selected, simply clear it.
       */
      if (selectedSlots.length === 1) {
        setForm((current) => ({
          ...current,
          slotIds: [],
        }));

        setNotice("");

        return;
      }

      const firstSlot = selectedSlots[0];
      const lastSlot =
        selectedSlots[selectedSlots.length - 1];

      /*
       * We only allow removing the first or last slot.
       * Removing a middle slot would create a gap.
       */
      if (
        slot.availability_slot_id ===
        firstSlot.availability_slot_id
      ) {
        const remainingSlots =
          selectedSlots.slice(1);

        setForm((current) => ({
          ...current,
          slotIds: remainingSlots.map((item) =>
            String(item.availability_slot_id)
          ),
        }));

        setNotice("");

        return;
      }

      if (
        slot.availability_slot_id ===
        lastSlot.availability_slot_id
      ) {
        const remainingSlots =
          selectedSlots.slice(
            0,
            selectedSlots.length - 1
          );

        setForm((current) => ({
          ...current,
          slotIds: remainingSlots.map((item) =>
            String(item.availability_slot_id)
          ),
        }));

        setNotice("");

        return;
      }

      setNotice(
        "You can only remove the first or last selected slot."
      );

      return;
    }

    /*
     * ---------------------------------------------------------
     * First selection
     * ---------------------------------------------------------
     */
    if (selectedSlots.length === 0) {
      setForm((current) => ({
        ...current,
        slotIds: [slotId],
      }));

      setNotice("");

      return;
    }

    const firstSlot = selectedSlots[0];
    const lastSlot =
      selectedSlots[selectedSlots.length - 1];

    /*
     * New slot can extend the booking backwards.
     */
    if (areConsecutive(slot, firstSlot)) {
      setForm((current) => ({
        ...current,
        slotIds: [
          slotId,
          ...current.slotIds,
        ],
      }));

      setNotice("");

      return;
    }

    /*
     * New slot can extend the booking forwards.
     */
    if (areConsecutive(lastSlot, slot)) {
      setForm((current) => ({
        ...current,
        slotIds: [
          ...current.slotIds,
          slotId,
        ],
      }));

      setNotice("");

      return;
    }

    /*
     * Prevent gaps.
     */
    setNotice(
      "Please select consecutive hourly slots. You cannot skip a time slot."
    );
  }

  function clearSelectedSlots() {
    setForm((current) => ({
      ...current,
      slotIds: [],
    }));

    setNotice("");
  }

  function formatSlotTime(slot) {
    const start = new Date(slot.starts_at);
    const end = new Date(slot.ends_at);

    return `${start.toLocaleTimeString(
      "en-IN",
      {
        hour: "numeric",
        minute: "2-digit",
      }
    )} – ${end.toLocaleTimeString(
      "en-IN",
      {
        hour: "numeric",
        minute: "2-digit",
      }
    )}`;
  }

  function formatTimeRange(slots) {
    if (!slots.length) {
      return "";
    }

    const firstSlot = slots[0];
    const lastSlot =
      slots[slots.length - 1];

    return `${new Date(
      firstSlot.starts_at
    ).toLocaleTimeString("en-IN", {
      hour: "numeric",
      minute: "2-digit",
    })} – ${new Date(
      lastSlot.ends_at
    ).toLocaleTimeString("en-IN", {
      hour: "numeric",
      minute: "2-digit",
    })}`;
  }

  function getSelectedStartAt() {
    const selectedSlots = getSelectedSlots();

    if (!selectedSlots.length) {
      return null;
    }

    return selectedSlots[0].starts_at;
  }

  function getSelectedEndAt() {
    const selectedSlots = getSelectedSlots();

    if (!selectedSlots.length) {
      return null;
    }

    return selectedSlots[
      selectedSlots.length - 1
    ].ends_at;
  }

  async function submitBooking(event) {
    event.preventDefault();

    if (submitting || bookingRequestInFlight.current) {
      return;
    }

    setNotice("");

    if (!form.farmId) {
      setNotice("Please select a farm.");
      return;
    }

    if (!form.addressId) {
      setNotice(
        "Please select a service address."
      );
      return;
    }

    if (!form.date) {
      setNotice("Please select a date.");
      return;
    }

    const selectedSlots =
      getSelectedSlots();

    if (selectedSlots.length === 0) {
      setNotice(
        "Please select at least one available time slot."
      );
      return;
    }

    if (
      !form.quantity ||
      Number(form.quantity) <= 0
    ) {
      setNotice(
        "Please enter a valid quantity."
      );
      return;
    }

    /*
     * Make absolutely sure the selected slots
     * are consecutive before submitting.
     */
    for (
      let index = 1;
      index < selectedSlots.length;
      index += 1
    ) {
      if (
        !areConsecutive(
          selectedSlots[index - 1],
          selectedSlots[index]
        )
      ) {
        setNotice(
          "Selected time slots must be consecutive."
        );
        return;
      }
    }

    bookingRequestInFlight.current = true;
    setSubmitting(true);

    try {
      const response = await fetch(
        `${API_URL}/my/bookings`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            ...(cropContext ? { crop_task_id: cropContext.crop_task_id, crop_request_key: cropRequestKey } : {}),
            supplier_service_id:
              service.supplier_service_id,

            farm_id: Number(form.farmId),

            service_address_id:
              Number(form.addressId),

            requested_start_at:
              getSelectedStartAt(),

            requested_end_at:
              getSelectedEndAt(),

            quantity: Number(form.quantity),

            customer_notes:
              form.notes || null,
          }),
        }
      );

      const result = await response.json();

      if (response.status === 401) {
        throw new Error(
          "Your session has expired. Please sign out and sign in again."
        );
      }

      if (!response.ok) {
        throw new Error(
          result.detail ||
            "Booking could not be created."
        );
      }

      onBookingCreated();
    } catch (error) {
      console.error(error);

      setNotice(
        error.message ||
          "Booking could not be created."
      );
    } finally {
      bookingRequestInFlight.current = false;
      setSubmitting(false);
    }
  }

  const selectedSlots =
    getSelectedSlots();

  const selectedHours =
    selectedSlots.length;

  const canSubmit =
    !loadingDetails &&
    !loadingSlots &&
    farms.length > 0 &&
    addresses.length > 0 &&
    Boolean(form.farmId) &&
    Boolean(form.addressId) &&
    Boolean(form.date) &&
    selectedSlots.length > 0;

  return (
    <section
      className="booking-panel"
      id="booking"
    >
      <div className="booking-heading">
        <div>
          <p className="eyebrow">{t("Create booking")}</p>

          <h2>{t("Book ")}{supplierDetails.serviceName}
          </h2>

          <p>
            <strong>
              {supplierDetails.supplierName}
            </strong>
          </p>

          <p>
            ⭐{" "}
            {Number(
              supplierDetails.averageRating || 0
            ).toFixed(1)}{" "}
            · ₹
            {Number(
              supplierDetails.basePrice
            ).toLocaleString("en-IN")}{" "}
            / {supplierDetails.pricingUnit}
          </p>
        </div>

        <button
          type="button"
          className="close-button"
          onClick={onClose}
        >{t("Close")}</button>
      </div>

      {loadingDetails ? <p className="booking-notice">{t("Loading your farms and service addresses...")}</p> : <form
          className="booking-form"
          onSubmit={submitBooking}
        >
          {cropContext ? <p className="full-width">{cropContext.title} ? {cropContext.crop_name}{cropContext.season ? ` ? ${cropContext.season}` : ""}<br />{[cropContext.farm_name, cropContext.plot_name, cropContext.block_name].filter(Boolean).join(" ? ")}</p> : <label>{t("Farm")}<select
              name="farmId"
              value={form.farmId}
              onChange={updateField}
              required
            >
              <option value="">{t("Select a farm")}</option>

              {Array.isArray(farms) && farms.map((farm) => (
                  <option
                    key={farm.farm_id}
                    value={farm.farm_id}
                  >
                    {farm.farm_name} —{" "}
                    {farm.location}
                  </option>
                ))}
            </select>
          </label>}

          <label>{t("Service address")}<select
              name="addressId"
              value={form.addressId}
              onChange={updateField}
              required
            >
              <option value="">{t("Select an address")}</option>

              {Array.isArray(addresses) && addresses.map((address) => (
                  <option
                    key={address.address_id}
                    value={address.address_id}
                  >
                    {address.label}:{" "}
                    {address.address_line1},{" "}
                    {address.village_or_city}
                  </option>
                ))}
            </select>
          </label>

          <label>{t("Date")}<input
              name="date"
              type="date"
              min={getTodayString()}
              value={form.date}
              onChange={updateField}
              required
            />
          </label>

          <label>{t("Quantity (")}{supplierDetails.pricingUnit})

            <input
              name="quantity"
              type="number"
              min="1"
              step="0.5"
              value={form.quantity}
              onChange={updateField}
              required
            />
          </label>

          <div className="booking-slots full-width">
            <div className="booking-slots-heading">
              <div>
                <h3>{t("Available time slots")}</h3>

                <p>{t("Select consecutive 1-hour slots from")}{" "}
                  {supplierDetails.supplierName}.
                </p>
              </div>

              {selectedSlots.length > 0 && <button
                  type="button"
                  className="secondary-button"
                  onClick={clearSelectedSlots}
                >{t("Clear")}</button>}
            </div>

            {!form.date ? <p className="booking-notice">{t("Select a date to see available time slots.")}</p> : loadingSlots ? <p className="booking-notice">{t("Loading available time slots...")}</p> : availableSlots.length === 0 ? <p className="booking-notice">{t("No available time slots for this date.")}</p> : <div className="booking-slot-grid">
                {availableSlots.map((slot) => {
                  const slotId = String(
                    slot.availability_slot_id
                  );

                  const selected =
                    form.slotIds.includes(slotId);

                  return (
                    <button
                      type="button"
                      key={
                        slot.availability_slot_id
                      }
                      className={`booking-slot ${
                        selected
                          ? "booking-slot-selected"
                          : ""
                      }`}
                      onClick={() =>
                        selectSlot(slot)
                      }
                    >
                      <strong>
                        {formatSlotTime(slot)}
                      </strong>

                      <span>
                        {slot.remaining_capacity}{" "}
                        {slot.remaining_capacity === 1 ? t("spot") : t("spots")}{" "}{t("remaining")}</span>
                    </button>
                  );
                })}
              </div>}

            {selectedSlots.length > 0 && <div className="selected-booking-slot">
                <strong>{t("Selected time")}</strong>

                <p>
                  {new Date(
                    selectedSlots[0].starts_at
                  ).toLocaleDateString(
                    "en-IN",
                    {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    }
                  )}{" "}
                  · {formatTimeRange(selectedSlots)}
                </p>

                <span>
                  {selectedHours}{" "}
                  {selectedHours === 1 ? t("hour") : t("hours")}{" "}{t("selected")}</span>
              </div>}
          </div>

          <label className="full-width">{t("Notes for the Service Provider")}<textarea
              name="notes"
              placeholder={t("Describe your requirement, field condition, or any instructions.")}
              value={form.notes}
              onChange={updateField}
              rows="4"
            />
          </label>

          <div className="booking-summary full-width">
            <span>{t("Estimated service price")}</span>

            <strong>
              ₹
              {(
                Number(
                  supplierDetails.basePrice
                ) *
                (Number(form.quantity) || 0)
              ).toLocaleString("en-IN")}
            </strong>
          </div>

          {selectedSlots.length > 0 && <div className="booking-confirmation full-width">
              <strong>{t("Booking with")}{" "}
                {supplierDetails.supplierName}
              </strong>

              <p>
                {supplierDetails.serviceName} ·{" "}
                {new Date(
                  selectedSlots[0].starts_at
                ).toLocaleDateString(
                  "en-IN",
                  {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                  }
                )}{" "}
                · {formatTimeRange(selectedSlots)}
              </p>

              <span>{t("Duration: ")}{selectedHours}{" "}
                {selectedHours === 1 ? t("hour") : t("hours")}
              </span>
            </div>}

          <button
            type="submit"
            className="primary-button full-width"
            disabled={
              submitting || !canSubmit
            }
          >
            {submitting ? t("Creating booking...") : t("Confirm booking")}
          </button>

          {notice && <p className="booking-notice full-width">
              {messageText(notice)}
            </p>}
        </form>}
    </section>
  );
}

export default BookingForm;
