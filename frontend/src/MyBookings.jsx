import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useEffect, useState } from "react";
import "./MyBookings.css";
import { BookingCropOrigin } from "./TaskServices";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function MyBookings({ onBack, farmerId, token, initialBookingId, onOpenCrop }) {
  useTranslation();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [ratings, setRatings] = useState({});
  const [reviewTexts, setReviewTexts] = useState({});
  const [reviewedBookings, setReviewedBookings] = useState({});
  const [error, setError] = useState("");

  // ---------------------------------------------------------
  // Reschedule state
  // ---------------------------------------------------------
  const [rescheduleBookingId, setRescheduleBookingId] =
    useState(null);

  const [rescheduleDate, setRescheduleDate] =
    useState("");

  const [rescheduleSlots, setRescheduleSlots] =
    useState([]);

  const [selectedRescheduleSlotIds, setSelectedRescheduleSlotIds] =
    useState([]);

  const [loadingRescheduleSlots, setLoadingRescheduleSlots] =
    useState(false);

  const [rescheduling, setRescheduling] =
    useState(false);

  const [rescheduleMessage, setRescheduleMessage] =
    useState("");

  // ---------------------------------------------------------
  // Load bookings
  // ---------------------------------------------------------
  useEffect(() => {
    async function loadBookings() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          `${API_URL}/farmers/${farmerId}/bookings`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error(
            "Could not load bookings."
          );
        }

        const data = await response.json();

        if (!Array.isArray(data)) {
          throw new Error(
            "Could not load bookings."
          );
        }

        setBookings(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    if (farmerId && token) {
      loadBookings();
    }
  }, [farmerId, token]);

  // ---------------------------------------------------------
  // Payment
  // ---------------------------------------------------------
  async function payForBooking(bookingId) {
    setMessage("");

    try {
      const response = await fetch(
        `${API_URL}/my/bookings/${bookingId}/payment`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            payment_method: "upi",
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(
          result.detail ||
            "Payment could not be completed."
        );
        return;
      }

      setBookings((currentBookings) =>
        currentBookings.map((booking) =>
          booking.booking_id === bookingId
            ? {
                ...booking,
                payment_status: "paid",
              }
            : booking
        )
      );

      setMessage(
        "Demo payment completed successfully."
      );
    } catch (error) {
      console.error(error);

      setMessage(
        "Payment could not be completed."
      );
    }
  }

  // ---------------------------------------------------------
  // Cancel booking
  // ---------------------------------------------------------
  async function cancelBooking(bookingId) {
    setMessage("");

    const confirmed = window.confirm(
      "Are you sure you want to cancel this booking?"
    );

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/my/bookings/${bookingId}/cancel`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(
          result.detail ||
            "Booking could not be cancelled."
        );
        return;
      }

      setBookings((currentBookings) =>
        currentBookings.map((booking) =>
          booking.booking_id === bookingId
            ? {
                ...booking,
                status: "cancelled",
              }
            : booking
        )
      );

      setMessage(
        "Booking cancelled successfully."
      );
    } catch (error) {
      console.error(error);

      setMessage(
        "Booking could not be cancelled."
      );
    }
  }

  // ---------------------------------------------------------
  // Review
  // ---------------------------------------------------------
  async function submitReview(bookingId) {
    setMessage("");

    try {
      const response = await fetch(
        `${API_URL}/my/bookings/${bookingId}/review`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            rating: Number(
              ratings[bookingId] || 5
            ),
            review_text:
              reviewTexts[bookingId] || null,
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        setMessage(
          result.detail ||
            "Review could not be submitted."
        );
        return;
      }

      setReviewedBookings((current) => ({
        ...current,
        [bookingId]: true,
      }));

      setMessage(
        "Thank you for your review."
      );
    } catch (error) {
      console.error(error);

      setMessage(
        "Review could not be submitted."
      );
    }
  }

  // =========================================================
  // RESCHEDULING
  // =========================================================

  function getBookingDurationHours(booking) {
    const start = new Date(
      booking.requested_start_at
    );

    const end = new Date(
      booking.requested_end_at
    );

    const durationMs =
      end.getTime() - start.getTime();

    return Math.round(
      durationMs / (1000 * 60 * 60)
    );
  }

  function getTodayString() {
    const today = new Date();

    const year = today.getFullYear();
    const month = String(
      today.getMonth() + 1
    ).padStart(2, "0");
    const day = String(
      today.getDate()
    ).padStart(2, "0");

    return `${year}-${month}-${day}`;
  }

  function closeReschedule() {
    setRescheduleBookingId(null);
    setRescheduleDate("");
    setRescheduleSlots([]);
    setSelectedRescheduleSlotIds([]);
    setRescheduleMessage("");
  }

  // ---------------------------------------------------------
  // Start rescheduling
  // ---------------------------------------------------------
  function openReschedule(booking) {
    setMessage("");
    setRescheduleMessage("");

    setRescheduleBookingId(
      booking.booking_id
    );

    setRescheduleDate("");
    setRescheduleSlots([]);
    setSelectedRescheduleSlotIds([]);
  }

  // ---------------------------------------------------------
  // Load available slots for reschedule date
  // ---------------------------------------------------------
  useEffect(() => {
    async function loadRescheduleSlots() {
      if (
        !rescheduleBookingId ||
        !rescheduleDate
      ) {
        setRescheduleSlots([]);
        return;
      }

      const booking = bookings.find(
        (item) =>
          item.booking_id ===
          rescheduleBookingId
      );

      if (!booking) {
        return;
      }

      /*
       * The farmer's booking response needs to contain
       * supplier_service_id so we can retrieve the
       * availability for the same service.
       */
      if (!booking.supplier_service_id) {
        setRescheduleMessage(
          "The booking does not contain the service information required for rescheduling."
        );

        setRescheduleSlots([]);
        return;
      }

      setLoadingRescheduleSlots(true);
      setRescheduleMessage("");
      setSelectedRescheduleSlotIds([]);

      try {
        const response = await fetch(
          `${API_URL}/supplier-services/${booking.supplier_service_id}/availability?date=${rescheduleDate}`
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

        const now = new Date();

        const futureSlots = data
          .filter((slot) => {
            const slotStart =
              new Date(slot.starts_at);

            return slotStart > now;
          })
          .sort(
            (a, b) =>
              new Date(a.starts_at) -
              new Date(b.starts_at)
          );

        setRescheduleSlots(
          futureSlots
        );

        if (futureSlots.length === 0) {
          setRescheduleMessage(
            "No available time slots for this date."
          );
        }
      } catch (error) {
        console.error(error);

        setRescheduleSlots([]);

        setRescheduleMessage(
          error.message ||
            "Could not load available time slots."
        );
      } finally {
        setLoadingRescheduleSlots(false);
      }
    }

    loadRescheduleSlots();
  }, [
    rescheduleBookingId,
    rescheduleDate,
    bookings,
  ]);

  // ---------------------------------------------------------
  // Get selected reschedule slots
  // ---------------------------------------------------------
  function getSelectedRescheduleSlots() {
    return rescheduleSlots
      .filter((slot) =>
        selectedRescheduleSlotIds.includes(
          String(slot.availability_slot_id)
        )
      )
      .sort(
        (a, b) =>
          new Date(a.starts_at) -
          new Date(b.starts_at)
      );
  }

  // ---------------------------------------------------------
  // Check consecutive slots
  // ---------------------------------------------------------
  function areConsecutive(slotA, slotB) {
    const endA = new Date(
      slotA.ends_at
    ).getTime();

    const startB = new Date(
      slotB.starts_at
    ).getTime();

    return endA === startB;
  }

  // ---------------------------------------------------------
  // Select reschedule slot
  // ---------------------------------------------------------
  function selectRescheduleSlot(
    slot,
    booking
  ) {
    setRescheduleMessage("");

    const slotId = String(
      slot.availability_slot_id
    );

    const selectedSlots =
      getSelectedRescheduleSlots();

    const requiredHours =
      getBookingDurationHours(
        booking
      );

    const alreadySelected =
      selectedRescheduleSlotIds.includes(
        slotId
      );

    // -------------------------------------------------------
    // Deselect
    // -------------------------------------------------------
    if (alreadySelected) {
      if (selectedSlots.length === 1) {
        setSelectedRescheduleSlotIds(
          []
        );
        return;
      }

      const firstSlot =
        selectedSlots[0];

      const lastSlot =
        selectedSlots[
          selectedSlots.length - 1
        ];

      if (
        slot.availability_slot_id ===
        firstSlot.availability_slot_id
      ) {
        const remaining =
          selectedSlots.slice(1);

        setSelectedRescheduleSlotIds(
          remaining.map((item) =>
            String(
              item.availability_slot_id
            )
          )
        );

        return;
      }

      if (
        slot.availability_slot_id ===
        lastSlot.availability_slot_id
      ) {
        const remaining =
          selectedSlots.slice(
            0,
            selectedSlots.length - 1
          );

        setSelectedRescheduleSlotIds(
          remaining.map((item) =>
            String(
              item.availability_slot_id
            )
          )
        );

        return;
      }

      setRescheduleMessage(
        "You can only remove the first or last selected slot."
      );

      return;
    }

    // -------------------------------------------------------
    // First selection
    // -------------------------------------------------------
    if (selectedSlots.length === 0) {
      setSelectedRescheduleSlotIds([
        slotId,
      ]);

      return;
    }

    const firstSlot =
      selectedSlots[0];

    const lastSlot =
      selectedSlots[
        selectedSlots.length - 1
      ];

    // -------------------------------------------------------
    // Extend backwards
    // -------------------------------------------------------
    if (
      areConsecutive(
        slot,
        firstSlot
      )
    ) {
      const newSelection = [
        slotId,
        ...selectedRescheduleSlotIds,
      ];

      if (
        newSelection.length >
        requiredHours
      ) {
        setRescheduleMessage(
          { key: "This booking is {{v0}} hour(s) long.", values: { v0: requiredHours } }
        );
        return;
      }

      setSelectedRescheduleSlotIds(
        newSelection
      );

      return;
    }

    // -------------------------------------------------------
    // Extend forwards
    // -------------------------------------------------------
    if (
      areConsecutive(
        lastSlot,
        slot
      )
    ) {
      const newSelection = [
        ...selectedRescheduleSlotIds,
        slotId,
      ];

      if (
        newSelection.length >
        requiredHours
      ) {
        setRescheduleMessage(
          { key: "This booking is {{v0}} hour(s) long.", values: { v0: requiredHours } }
        );
        return;
      }

      setSelectedRescheduleSlotIds(
        newSelection
      );

      return;
    }

    setRescheduleMessage(
      "Please select consecutive hourly slots. You cannot skip a time slot."
    );
  }

  // ---------------------------------------------------------
  // Format time
  // ---------------------------------------------------------
  function formatTimeRange(slots) {
    if (!slots.length) {
      return "";
    }

    const firstSlot = slots[0];

    const lastSlot =
      slots[slots.length - 1];

    const start =
      new Date(
        firstSlot.starts_at
      ).toLocaleTimeString(
        "en-IN",
        {
          hour: "numeric",
          minute: "2-digit",
        }
      );

    const end =
      new Date(
        lastSlot.ends_at
      ).toLocaleTimeString(
        "en-IN",
        {
          hour: "numeric",
          minute: "2-digit",
        }
      );

    return `${start} – ${end}`;
  }

  function formatSlotTime(slot) {
    const start =
      new Date(
        slot.starts_at
      ).toLocaleTimeString(
        "en-IN",
        {
          hour: "numeric",
          minute: "2-digit",
        }
      );

    const end =
      new Date(
        slot.ends_at
      ).toLocaleTimeString(
        "en-IN",
        {
          hour: "numeric",
          minute: "2-digit",
        }
      );

    return `${start} – ${end}`;
  }

  // ---------------------------------------------------------
  // Confirm reschedule
  // ---------------------------------------------------------
  async function confirmReschedule(
    booking
  ) {
    setRescheduleMessage("");

    const selectedSlots =
      getSelectedRescheduleSlots();

    const requiredHours =
      getBookingDurationHours(
        booking
      );

    if (
      selectedSlots.length !==
      requiredHours
    ) {
      setRescheduleMessage(
        { key: "Please select exactly {{v0}} consecutive hour(s).", values: { v0: requiredHours } }
      );

      return;
    }

    // Final consecutive validation
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
        setRescheduleMessage(
          "Selected slots must be consecutive."
        );

        return;
      }
    }

    const newStart =
      selectedSlots[0].starts_at;

    const newEnd =
      selectedSlots[
        selectedSlots.length - 1
      ].ends_at;

    const confirmed =
      window.confirm(
        `Reschedule this booking to ${formatTimeRange(
          selectedSlots
        )}?`
      );

    if (!confirmed) {
      return;
    }

    setRescheduling(true);

    try {
      const response = await fetch(
        `${API_URL}/my/bookings/${booking.booking_id}/reschedule`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            requested_start_at:
              newStart,
            requested_end_at:
              newEnd,
          }),
        }
      );

      const result =
        await response.json();

      if (!response.ok) {
        setRescheduleMessage(
          result.detail ||
            "Booking could not be rescheduled."
        );

        return;
      }

      // Update booking locally
      setBookings((currentBookings) =>
        currentBookings.map(
          (currentBooking) =>
            currentBooking.booking_id ===
            booking.booking_id
              ? {
                  ...currentBooking,
                  requested_start_at:
                    result.new_start_at,
                  requested_end_at:
                    result.new_end_at,
                }
              : currentBooking
        )
      );

      setRescheduleMessage(
        "Booking rescheduled successfully."
      );

      setSelectedRescheduleSlotIds([]);

      /*
       * Close the reschedule section after
       * a short delay so the farmer can see
       * the success message.
       */
      setTimeout(() => {
        setRescheduleBookingId(null);
        setRescheduleDate("");
        setRescheduleSlots([]);
        setSelectedRescheduleSlotIds([]);
        setRescheduleMessage("");
      }, 1800);
    } catch (error) {
      console.error(error);

      setRescheduleMessage(
        error.message ||
          "Booking could not be rescheduled."
      );
    } finally {
      setRescheduling(false);
    }
  }

  // =========================================================
  // RENDER
  // =========================================================

  return (
    <div className="bookings-page">
      <main className="bookings-content">
        <div className="bookings-top-bar">
        <button
          aria-label={t("Back to marketplace")}
          className="bookings-back-button"
          onClick={onBack}
        >
          ←
        </button>

          <h1>{t("My Bookings")}</h1>

          <div aria-hidden="true" className="bookings-top-bar-spacer" />
        </div>

        <div className="bookings-intro">
          <h2>{t("Your bookings")}</h2>

          <p>{t("Track your requested and completed agricultural services.")}</p>
        </div>

        {loading && <p>{t("Loading bookings…")}</p>}

        {error && <p className="error-message">
            {messageText(error)}
          </p>}

        <div className="booking-list">
          {bookings.filter((b) => !initialBookingId || b.booking_id === initialBookingId).map((booking) => {
            const canReschedule = [
              "pending",
              "quoted",
              "confirmed",
            ].includes(
              booking.status
            );

            const isRescheduling =
              rescheduleBookingId ===
              booking.booking_id;

            const selectedSlots =
              isRescheduling
                ? getSelectedRescheduleSlots()
                : [];

            const durationHours =
              getBookingDurationHours(
                booking
              );

            return (
              <article
                className="booking-card"
                key={booking.booking_id}
              >
                <BookingCropOrigin booking={booking} onOpenCrop={onOpenCrop} />
                <div className="booking-card-summary">
                  <div className="booking-card-heading">
                  <h2>
                    {booking.service_names}
                  </h2>

                    <span
                      className={`status status-${booking.status}`}
                    >
                      {booking.status}
                    </span>
                  </div>

                  <p className="booking-provider">
                    {booking.supplier_name}
                  </p>

                  <p>{t("Scheduled:")}{" "}
                    {new Date(
                      booking.requested_start_at
                    ).toLocaleString(
                      "en-IN"
                    )}
                    {" – "}
                    {new Date(
                      booking.requested_end_at
                    ).toLocaleTimeString(
                      "en-IN",
                      {
                        hour: "numeric",
                        minute: "2-digit",
                      }
                    )}
                  </p>

                  <p>{t("Duration:")}{" "}
                    {durationHours}{" "}
                    {durationHours === 1 ? t("hour") : t("hours")}
                  </p>

                  <div className="booking-financials">
                  <strong>
                    ₹
                    {Number(
                      booking.total_amount
                    ).toLocaleString(
                      "en-IN"
                    )}
                  </strong>

                  <small>{t("Payment:")}{" "}
                    {booking.payment_status}
                  </small>
                  </div>

                  <p className="booking-number">
                    {booking.booking_number}
                  </p>
                </div>

                <div className="booking-card-actions">

                  {/* ---------------------------------------
                      RESCHEDULE BUTTON
                  ---------------------------------------- */}
                  {canReschedule && <button
                      className="reschedule-button"
                      onClick={() =>
                        isRescheduling
                          ? closeReschedule()
                          : openReschedule(
                              booking
                            )
                      }
                    >
                      {isRescheduling ? t("Close reschedule") : t("Reschedule")}
                    </button>}

                  {/* ---------------------------------------
                      CANCEL
                  ---------------------------------------- */}
                  {[
                    "pending",
                    "quoted",
                    "confirmed",
                  ].includes(
                    booking.status
                  ) && <button
                      className="cancel-button"
                      onClick={() =>
                        cancelBooking(
                          booking.booking_id
                        )
                      }
                    >{t("Cancel booking")}</button>}

                  {/* ---------------------------------------
                      PAYMENT
                  ---------------------------------------- */}
                  {booking.payment_status ===
                    "unpaid" &&
                    [
                      "confirmed",
                      "in_progress",
                      "completed",
                    ].includes(
                      booking.status
                    ) && <button
                        className="book-button"
                        onClick={() =>
                          payForBooking(
                            booking.booking_id
                          )
                        }
                      >{t("Pay now")}</button>}

                  {/* ---------------------------------------
                      REVIEW
                  ---------------------------------------- */}
                  {booking.status ===
                    "completed" &&
                    !reviewedBookings[
                      booking.booking_id
                    ] && <div className="review-box">
                        <select
                          value={
                            ratings[
                              booking.booking_id
                            ] || 5
                          }
                          onChange={(
                            event
                          ) =>
                            setRatings(
                              (
                                current
                              ) => ({
                                ...current,
                                [booking.booking_id]:
                                  event
                                    .target
                                    .value,
                              })
                            )
                          }
                        >
                          <option value="5">{t("5 stars")}</option>
                          <option value="4">{t("4 stars")}</option>
                          <option value="3">{t("3 stars")}</option>
                          <option value="2">{t("2 stars")}</option>
                          <option value="1">{t("1 star")}</option>
                        </select>

                        <input
                          placeholder={t("Write a review (optional)")}
                          value={
                            reviewTexts[
                              booking.booking_id
                            ] || ""
                          }
                          onChange={(
                            event
                          ) =>
                            setReviewTexts(
                              (
                                current
                              ) => ({
                                ...current,
                                [booking.booking_id]:
                                  event
                                    .target
                                    .value,
                              })
                            )
                          }
                        />

                        <button
                          className="book-button"
                          onClick={() =>
                            submitReview(
                              booking.booking_id
                            )
                          }
                        >{t("Submit review")}</button>
                      </div>}
                </div>

                {/* =====================================
                      RESCHEDULE PANEL
                  ====================================== */}
                  {isRescheduling && <div className="reschedule-panel">
                      <div className="reschedule-heading">
                        <div>
                          <strong>{t("Reschedule booking")}</strong>

                          <p>{t("Select a new")}{" "}
                            {durationHours}{t("-hour consecutive period.")}</p>
                        </div>

                        <button
                          type="button"
                          className="reschedule-close-button"
                          onClick={
                            closeReschedule
                          }
                        >
                          ×
                        </button>
                      </div>

                      <label>{t("New date")}<input
                          type="date"
                          min={getTodayString()}
                          value={
                            rescheduleDate
                          }
                          onChange={(
                            event
                          ) => {
                            setRescheduleDate(
                              event.target
                                .value
                            );

                            setSelectedRescheduleSlotIds(
                              []
                            );

                            setRescheduleMessage(
                              ""
                            );
                          }}
                        />
                      </label>

                      {!rescheduleDate ? <p className="reschedule-notice">{t("Select a date to see available time slots.")}</p> : loadingRescheduleSlots ? <p className="reschedule-notice">{t("Loading available time slots...")}</p> : rescheduleSlots.length ===
                        0 ? <p className="reschedule-notice">
                          {rescheduleMessage || t("No available time slots for this date.")}
                        </p> : <>
                          <div className="reschedule-slot-grid">
                            {rescheduleSlots.map(
                              (slot) => {
                                const selected =
                                  selectedRescheduleSlotIds.includes(
                                    String(
                                      slot.availability_slot_id
                                    )
                                  );

                                return (
                                  <button
                                    type="button"
                                    key={
                                      slot.availability_slot_id
                                    }
                                    className={`reschedule-slot ${
                                      selected
                                        ? "reschedule-slot-selected"
                                        : ""
                                    }`}
                                    onClick={() =>
                                      selectRescheduleSlot(
                                        slot,
                                        booking
                                      )
                                    }
                                  >
                                    <strong>
                                      {formatSlotTime(
                                        slot
                                      )}
                                    </strong>

                                    <span>
                                      {
                                        slot.remaining_capacity
                                      }{" "}
                                      {slot.remaining_capacity ===
                                      1 ? t("spot") : t("spots")}{" "}{t("remaining")}</span>
                                  </button>
                                );
                              }
                            )}
                          </div>

                          {selectedSlots.length >
                            0 && (
                            <div className="reschedule-selection">
                              <strong>{t("New time")}</strong>

                              <p>
                                {new Date(
                                  selectedSlots[0].starts_at
                                ).toLocaleDateString(
                                  "en-IN",
                                  {
                                    day: "2-digit",
                                    month:
                                      "short",
                                    year: "numeric",
                                  }
                                )}{" "}
                                ·{" "}
                                {formatTimeRange(
                                  selectedSlots
                                )}
                              </p>

                              <span>
                                {
                                  selectedSlots.length
                                }{" "}{t("of")}{" "}
                                {
                                  durationHours
                                }{" "}{t("hours selected")}</span>
                            </div>
                          )}

                          {rescheduleMessage && (
                            <p className="reschedule-message">
                              {
                                messageText(rescheduleMessage)
                              }
                            </p>
                          )}

                          <button
                            type="button"
                            className="book-button reschedule-confirm-button"
                            disabled={
                              rescheduling ||
                              selectedSlots.length !==
                                durationHours
                            }
                            onClick={() =>
                              confirmReschedule(
                                booking
                              )
                            }
                          >
                            {rescheduling ? t("Rescheduling...") : t("Confirm reschedule")}
                          </button>
                        </>}

                      {rescheduleMessage &&
                        rescheduleSlots.length >
                          0 && <p className="reschedule-message">
                            {
                              messageText(rescheduleMessage)
                            }
                          </p>}
                    </div>}
              </article>
            );
          })}
        </div>

        {!loading &&
          !error &&
          bookings.length === 0 && <p>{t("You have no bookings yet.")}</p>}

        {message && <p className="booking-notice">
            {messageText(message)}
          </p>}
      </main>
    </div>
  );
}

export default MyBookings;
