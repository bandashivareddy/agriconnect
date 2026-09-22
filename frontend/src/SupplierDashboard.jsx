import { BookingCropOrigin } from "./TaskServices";
import { useEffect, useState } from "react";
import "./SupplierDashboard.css";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function SupplierDashboard({
  token,
  onBack,
  onManageServices,
  onManageAvailability,
  onManageEquipment,
  onManageProfile,
  onManageVerification,
}) {
  const [dashboard, setDashboard] = useState(null);
  const [services, setServices] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentMessage, setDocumentMessage] = useState("");
  const [submittingDocument, setSubmittingDocument] = useState(false);

  // Booking-specific message
  const [bookingMessage, setBookingMessage] = useState({
    bookingId: null,
    text: "",
  });

  const [documentForm, setDocumentForm] = useState({
    documentType: "",
    fileName: "",
    fileUrl: "",
  });
  const showLegacyServiceWorkflow = false;

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  // =========================================================
  // LOAD SUPPLIER DATA
  // =========================================================

  useEffect(() => {
    async function loadSupplierData() {
      try {
        const [
          dashboardResponse,
          servicesResponse,
          bookingsResponse,
        ] = await Promise.all([
          fetch(`${API_URL}/supplier/dashboard`, { headers }),
          fetch(`${API_URL}/supplier/services`, { headers }),
          fetch(`${API_URL}/supplier/bookings`, { headers }),
        ]);

        const [
          dashboardData,
          serviceData,
          bookingData,
        ] = await Promise.all([
          dashboardResponse.json(),
          servicesResponse.json(),
          bookingsResponse.json(),
        ]);

        if (!servicesResponse.ok || !Array.isArray(serviceData)) {
          throw new Error("Could not load supplier services.");
        }

        if (!bookingsResponse.ok || !Array.isArray(bookingData)) {
          throw new Error("Could not load incoming bookings.");
        }

        setDashboard(dashboardData);
        setServices(serviceData);
        setBookings(bookingData);
      } catch (error) {
        console.error("Supplier dashboard load error:", error);
      }
    }

    loadSupplierData();
  }, [token]);

  // =========================================================
  // LOAD PROVIDER VERIFICATION DOCUMENTS
  // =========================================================

  useEffect(() => {
    async function loadProviderDocuments() {
      setDocumentsLoading(true);
      setDocumentMessage("");

      try {
        const response = await fetch(
          `${API_URL}/provider/documents`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        const data = await response.json();

        if (!response.ok || !Array.isArray(data)) {
          throw new Error(
            data.detail || "Could not load verification documents."
          );
        }

        setDocuments(data);
      } catch (error) {
        console.error("Provider document load error:", error);
        setDocuments([]);
        setDocumentMessage(
          error.message || "Could not load verification documents."
        );
      } finally {
        setDocumentsLoading(false);
      }
    }

    loadProviderDocuments();
  }, [token]);

  // =========================================================
  // PROVIDER VERIFICATION DOCUMENTS
  // =========================================================

  function updateDocumentField(event) {
    const { name, value } = event.target;

    setDocumentForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function submitDocument(event) {
    event.preventDefault();
    setDocumentMessage("");
    setSubmittingDocument(true);

    try {
      const response = await fetch(
        `${API_URL}/provider/documents`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            document_type: documentForm.documentType,
            file_name: documentForm.fileName,
            file_url: documentForm.fileUrl,
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || "Verification document could not be submitted."
        );
      }

      setDocuments((current) => [result, ...current]);
      setDocumentForm({
        documentType: "",
        fileName: "",
        fileUrl: "",
      });
      setDocumentMessage(
        "Document submitted for verification."
      );
    } catch (error) {
      console.error("Provider document submission error:", error);
      setDocumentMessage(
        error.message || "Verification document could not be submitted."
      );
    } finally {
      setSubmittingDocument(false);
    }
  }

  // =========================================================
  // UPDATE BOOKING STATUS
  // =========================================================

  async function updateBookingStatus(bookingId, newStatus) {
    // Clear any previous booking message
    setBookingMessage({
      bookingId: null,
      text: "",
    });

    try {
      const response = await fetch(
        `${API_URL}/supplier/bookings/${bookingId}/status`,
        {
          method: "PUT",
          headers,
          body: JSON.stringify({
            new_status: newStatus,
            notes: `Updated by supplier to ${newStatus}.`,
          }),
        }
      );

      const result = await response.json();

      // =====================================================
      // BACKEND ERROR
      // =====================================================

      if (!response.ok) {
        setBookingMessage({
          bookingId,
          text:
            result.detail ||
            "Booking status could not be updated.",
        });

        return;
      }

      // =====================================================
      // SUCCESSFULLY UPDATE LOCAL BOOKING STATUS
      // =====================================================

      setBookings((current) =>
        current.map((booking) =>
          booking.booking_id === bookingId
            ? {
                ...booking,
                status: result.status,
              }
            : booking
        )
      );

      // =====================================================
      // BOOKING-SPECIFIC SUCCESS MESSAGE
      // =====================================================

      setBookingMessage({
        bookingId,
        text: `Booking ${result.booking_number} is now ${result.status}.`,
      });
    } catch (error) {
      console.error(
        "Booking status update error:",
        error
      );

      setBookingMessage({
        bookingId,
        text:
          error.message ||
          "Could not update the booking status.",
      });
    }
  }

  // =========================================================
  // FORMAT BOOKING DATE
  // =========================================================

  function formatBookingDate(dateValue) {
    if (!dateValue) {
      return "Schedule not specified";
    }

    return new Date(dateValue).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  // =========================================================
  // PAGE
  // =========================================================

  return (
    <main className="supplier-page">

      {/* =====================================================
          TOP NAVIGATION
          ===================================================== */}

      <div className="supplier-topbar">
        <button
          className="back-button"
          onClick={onBack}
        >
          ← Marketplace
        </button>
      </div>

      <section className="supplier-content">

        {/* ===================================================
            SUPPLIER HEADER
            =================================================== */}

        <header className="supplier-hero">
          <p className="eyebrow">
            Provider Dashboard
          </p>

          <h1>
            {dashboard?.supplier?.business_name ||
              "Your business"}
          </h1>

          <p className="supplier-intro">
            Manage your services, availability and incoming bookings.
          </p>
        </header>

        {/* ===================================================
            SUMMARY
            =================================================== */}

        <section className="supplier-summary">

          <div className="supplier-summary-card">
            <span>Active services</span>

            <strong>
              {services.length}
            </strong>
          </div>

          <div className="supplier-summary-card">
            <span>Average rating</span>

            <strong>
              ★{" "}
              {Number(
                dashboard?.supplier?.average_rating || 0
              ).toFixed(1)}
            </strong>
          </div>

        </section>

        <section className="supplier-section provider-workspace-section">
          <div className="supplier-section-heading">
            <div>
              <p className="eyebrow">Provider workspace</p>
              <h2>Manage your work</h2>
              <p>Manage your services, availability and incoming bookings.</p>
            </div>
          </div>

          <div className="provider-workspace-list">
            <article className="provider-workspace-card">
              <div><h3>My Services</h3><p>Manage the agricultural services you offer.</p></div>
              <button className="secondary-action" type="button" onClick={onManageServices}>Manage →</button>
            </article>
            <article className="provider-workspace-card">
              <div><h3>My Availability</h3><p>Manage when farmers can book your services.</p></div>
              <button className="secondary-action" type="button" onClick={onManageAvailability}>Manage →</button>
            </article>
            <article className="provider-workspace-card">
              <div><h3>My Equipment</h3><p>Optional equipment used for your services.</p></div>
              <button className="secondary-action" type="button" onClick={onManageEquipment}>Manage →</button>
            </article>
            <article className="provider-workspace-card">
              <div><h3>Provider Profile</h3><p>Manage your provider/business information.</p></div>
              <button className="secondary-action" type="button" onClick={onManageProfile}>Manage →</button>
            </article>
            <article className="provider-workspace-card">
              <div><h3>Verification</h3><p>Manage your verification documents and review status.</p></div>
              <button className="secondary-action" type="button" onClick={onManageVerification}>Manage →</button>
            </article>
          </div>
        </section>

        {/* ===================================================
            PROVIDER VERIFICATION DOCUMENTS
            =================================================== */}

        <section className="supplier-section provider-documents-section provider-documents-section-legacy">

          <div className="supplier-section-heading">
            <div>
              <p className="eyebrow">
                Provider validation
              </p>

              <h2>
                Verification documents
              </h2>

              <p>
                Submit a document that helps us verify your identity,
                equipment or service. GST registration is not required.
              </p>
            </div>
          </div>

          <form
            onSubmit={submitDocument}
            className="supplier-form provider-document-form"
          >
            <label>
              Document type

              <select
                name="documentType"
                value={documentForm.documentType}
                onChange={updateDocumentField}
                required
              >
                <option value="" disabled>
                  Select a document type
                </option>
                <optgroup label="Identity / eligibility">
                  <option value="driving_licence">
                    Driving Licence
                  </option>
                  <option value="voter_id">
                    Voter ID
                  </option>
                  <option value="other_government_id">
                    Other Government ID
                  </option>
                </optgroup>
                <optgroup label="Equipment / service proof">
                  <option value="vehicle_equipment_rc">
                    Vehicle / Equipment RC
                  </option>
                  <option value="equipment_ownership_proof">
                    Equipment Ownership Proof
                  </option>
                  <option value="service_trade_certificate">
                    Service / Trade Certificate
                  </option>
                </optgroup>
                <optgroup label="Optional business documents">
                  <option value="gst_certificate">
                    GST Certificate
                  </option>
                  <option value="business_registration">
                    Business Registration
                  </option>
                </optgroup>
                <option value="other_supporting_document">
                  Other Supporting Document
                </option>
              </select>
            </label>

            <label>
              File name

              <input
                name="fileName"
                value={documentForm.fileName}
                onChange={updateDocumentField}
                placeholder="document.pdf"
                maxLength="255"
                required
              />
            </label>

            <label className="supplier-full-width">
              Temporary internal document reference or URL

              <input
                name="fileUrl"
                value={documentForm.fileUrl}
                onChange={updateDocumentField}
                placeholder="Enter the temporary document reference or URL"
                required
              />
            </label>

            <p className="provider-document-reference-note supplier-full-width">
              This is a temporary internal reference for pilot review.
              Secure file upload and storage are not available yet.
            </p>

            <button
              className="primary-button supplier-full-width"
              type="submit"
              disabled={submittingDocument}
            >
              {submittingDocument
                ? "Submitting document..."
                : "Submit for verification"}
            </button>
          </form>

          {documentMessage && (
            <p className="supplier-message">
              {documentMessage}
            </p>
          )}

          <div className="provider-document-list">
            <h3>Your submitted documents</h3>

            {documentsLoading ? (
              <p className="provider-document-loading">
                Loading verification documents...
              </p>
            ) : documents.length === 0 ? (
              <div className="supplier-empty-state">
                <strong>No verification documents submitted.</strong>

                <p>
                  Add a document reference above for admin review.
                </p>
              </div>
            ) : (
              documents.map((document) => (
                <article
                  className="provider-document-card"
                  key={document.document_id}
                >
                  <div className="provider-document-card-header">
                    <div>
                      <h4>
                        {document.document_type_label ||
                          document.document_type}
                      </h4>
                      <p>{document.file_name}</p>
                    </div>

                    <span
                      className={`provider-document-status provider-document-status-${document.verification_status}`}
                    >
                      {document.verification_status}
                    </span>
                  </div>

                  <p className="provider-document-reference">
                    <strong>Document reference:</strong>{" "}
                    {document.file_url}
                  </p>
                </article>
              ))
            )}
          </div>

        </section>

        {/* ===================================================
            INCOMING BOOKINGS
            =================================================== */}

        <section className="supplier-section">

          <div className="supplier-section-heading">
            <div>
              <p className="eyebrow">
                Bookings
              </p>

              <h2>
                Incoming bookings
              </h2>
            </div>

            {bookings.length > 0 && (
              <span className="booking-count">
                {bookings.length}{" "}
                {bookings.length === 1
                  ? "booking"
                  : "bookings"}
              </span>
            )}
          </div>

          {bookings.length === 0 ? (

            <div className="supplier-empty-state">
              <strong>
                No incoming bookings yet.
              </strong>

              <p>
                New farmer bookings will appear here.
              </p>
            </div>

          ) : (

            <div className="supplier-booking-list">

              {bookings.map((booking) => (

                <article
                  className="supplier-booking-card"
                  key={booking.booking_id}
                >

                  {/* =========================================
                      BOOKING INFORMATION
                      ========================================= */}

                  <div className="supplier-booking-main">

                    <div className="supplier-booking-header">

                      <span
                        className={`status status-${booking.status}`}
                      >
                        {booking.status}
                      </span>

                      <span className="supplier-booking-number">
                        {booking.booking_number}
                      </span>
                      <BookingCropOrigin booking={booking} />

                    </div>

                    {/* =======================================
                        TITLE + PRICE
                        ======================================= */}

                    <div className="supplier-booking-title-row">

                      <h3>
                        {booking.service_names}
                      </h3>

                      <div className="supplier-booking-price">
                        ₹
                        {Number(
                          booking.total_amount
                        ).toLocaleString("en-IN")}
                      </div>

                    </div>

                    {/* =======================================
                        BOOKING DETAILS
                        ======================================= */}

                    <div className="supplier-booking-details">

                      <p>
                        <strong>
                          {booking.farmer_name}
                        </strong>

                        {booking.farmer_phone && (
                          <>
                            {" "}
                            · {booking.farmer_phone}
                          </>
                        )}
                      </p>

                      <p>
                        <strong>Farm:</strong>{" "}
                        {booking.farm_name ||
                          "Farm not specified"}

                        {booking.farm_location
                          ? ` — ${booking.farm_location}`
                          : ""}
                      </p>

                      <p>
                        <strong>Scheduled:</strong>{" "}
                        {formatBookingDate(
                          booking.requested_start_at
                        )}
                      </p>

                      {booking.customer_notes && (
                        <p className="supplier-booking-note">
                          <strong>
                            Farmer note:
                          </strong>{" "}
                          {booking.customer_notes}
                        </p>
                      )}

                    </div>

                    {/* =======================================
                        BOOKING-SPECIFIC MESSAGE
                        ======================================= */}

                    {bookingMessage.bookingId ===
                      booking.booking_id &&
                      bookingMessage.text && (
                        <p className="supplier-booking-message">
                          {bookingMessage.text}
                        </p>
                      )}

                    {/* =======================================
                        BOOKING ACTIONS
                        ======================================= */}

                    <div className="supplier-booking-actions">

                      {/* PENDING */}

                      {booking.status === "pending" && (
                        <div className="booking-action-row">

                          <button
                            className="book-button"
                            onClick={() =>
                              updateBookingStatus(
                                booking.booking_id,
                                "confirmed"
                              )
                            }
                          >
                            Accept
                          </button>

                          <button
                            className="secondary-action"
                            onClick={() =>
                              updateBookingStatus(
                                booking.booking_id,
                                "rejected"
                              )
                            }
                          >
                            Reject
                          </button>

                        </div>
                      )}

                      {/* CONFIRMED */}

                      {booking.status === "confirmed" && (
                        <button
                          className="book-button"
                          onClick={() =>
                            updateBookingStatus(
                              booking.booking_id,
                              "in_progress"
                            )
                          }
                        >
                          Start work
                        </button>
                      )}

                      {/* IN PROGRESS */}

                      {booking.status === "in_progress" && (
                        <button
                          className="book-button"
                          onClick={() =>
                            updateBookingStatus(
                              booking.booking_id,
                              "completed"
                            )
                          }
                        >
                          Mark complete
                        </button>
                      )}

                    </div>

                  </div>

                </article>

              ))}

            </div>

          )}

        </section>

        {/* ===================================================
            MY SERVICES
            =================================================== */}

        {showLegacyServiceWorkflow && (
          <>

        <section className="supplier-section">

          <div className="supplier-section-heading">

            <div>

              <p className="eyebrow">
                Marketplace listings
              </p>

              <h2>
                My services
              </h2>

              <p>
                Services currently offered to farmers.
              </p>

            </div>

            <button
              className="secondary-action"
              type="button"
              onClick={onManageServices}
            >
              Manage →
            </button>

          </div>

          {services.length === 0 ? (

            <div className="supplier-empty-state">

              <strong>
                No services added yet.
              </strong>

              <p>
                Add your first agricultural service below.
              </p>

            </div>

          ) : (

            <div className="supplier-service-grid">

              {services.map((service) => (

                <article
                  className="supplier-service-card"
                  key={service.supplier_service_id}
                >

                  <div className="supplier-service-card-top">

                    <span>
                      {service.parent_category_name ||
                        "Agricultural service"}
                    </span>

                  </div>

                  <h3>
                    {service.service_name}
                  </h3>

                  <p>
                    {service.description ||
                      "No description provided."}
                  </p>

                  <div className="supplier-service-price">
                    {formatPrice(service)}
                  </div>

                </article>

              ))}

            </div>

          )}

        </section>

        {/* ===================================================
            ADD SERVICE
            =================================================== */}

        <section className="supplier-section add-service">

          <div className="supplier-section-heading">

            <div>

              <p className="eyebrow">
                Marketplace listing
              </p>

              <h2>
                Add a service
              </h2>

              <p>
                Select a service you provide and tell farmers
                how you charge.
              </p>

            </div>

          </div>

          <form
            onSubmit={addService}
            className="supplier-form"
          >

            {/* SERVICE */}

            <label>
              Service

              <select
                name="categoryId"
                value={form.categoryId}
                onChange={updateField}
                required
              >

                <option value="" disabled>
                  Select a service
                </option>

                {parentCategories.map((parent) => {

                  const parentServices =
                    childServices.filter(
                      (service) =>
                        service.parent_category_id ===
                        parent.category_id
                    );

                  if (parentServices.length === 0) {
                    return null;
                  }

                  return (
                    <optgroup
                      key={parent.category_id}
                      label={parent.category_name}
                    >
                      {parentServices.map((service) => (
                        <option
                          key={service.category_id}
                          value={service.category_id}
                        >
                          {service.category_name}
                        </option>
                      ))}
                    </optgroup>
                  );
                })}

                {/* Fallback for category data that does not
                    include parent relationships. */}

                {parentCategories.length === 0 &&
                  childServices.map((service) => (
                    <option
                      key={service.category_id}
                      value={service.category_id}
                    >
                      {service.category_name}
                    </option>
                  ))}

              </select>
            </label>

            {/* PRICING UNIT */}

            <label>
              Pricing unit

              <select
                name="pricingUnit"
                value={form.pricingUnit}
                onChange={updateField}
              >
                <option value="acre">
                  Per acre
                </option>

                <option value="hour">
                  Per hour
                </option>

                <option value="day">
                  Per day
                </option>

                <option value="trip">
                  Per trip
                </option>

                <option value="fixed">
                  Fixed price
                </option>

                <option value="custom">
                  Custom quote
                </option>
              </select>
            </label>

            {/* BASE PRICE */}

            <label>
              Base price (₹)

              <input
                name="basePrice"
                type="number"
                min="0"
                value={form.basePrice}
                onChange={updateField}
                disabled={
                  form.pricingUnit === "custom"
                }
                required={
                  form.pricingUnit !== "custom"
                }
              />
            </label>

            {/* MINIMUM CHARGE */}

            <label>
              Minimum charge (₹)

              <input
                name="minimumCharge"
                type="number"
                min="0"
                value={form.minimumCharge}
                onChange={updateField}
              />
            </label>

            {/* DURATION */}

            <label>
              Estimated duration (minutes)

              <input
                name="duration"
                type="number"
                min="1"
                value={form.duration}
                onChange={updateField}
              />
            </label>

            {/* DESCRIPTION */}

            <label className="supplier-full-width">
              Description

              <textarea
                name="description"
                rows="3"
                value={form.description}
                onChange={updateField}
                placeholder="Explain what is included in the service."
              />
            </label>

            {/* SUBMIT */}

            <button
              className="primary-button supplier-full-width"
              type="submit"
            >
              Add service
            </button>

          </form>

          {/* GENERAL SERVICE MESSAGE */}

          {message && (
            <p className="supplier-message">
              {message}
            </p>
          )}

        </section>
          </>
        )}

      </section>

    </main>
  );
}

export default SupplierDashboard;
