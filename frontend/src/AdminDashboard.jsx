import { useCallback, useEffect, useState } from "react";
import "./AdminDashboard.css";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function AdminDashboard({
  user,
  token,
  metrics,
  loading,
  error,
  onBack,
  logoutAction,
  onManageSops,
  onManageFieldWork,
  onOfficerApplications,
  onManageCatalogue,
}) {
  const [providerQueue, setProviderQueue] = useState([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState(null);
  const [providerDetail, setProviderDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [verificationMessage, setVerificationMessage] = useState({
    type: "",
    text: "",
  });
  const [verificationAction, setVerificationAction] = useState("");

  const dashboardMetrics = [
    {
      label: "Users",
      value: metrics?.total_users ?? "—",
      description: "Platform users",
    },
    {
      label: "Service Providers",
      value: metrics?.total_suppliers ?? "—",
      description: "Service Provider accounts",
    },
    {
      label: "Services",
      value: metrics?.active_services  ?? "—",
      description: "Active marketplace services",
    },
    {
      label: "Bookings",
      value: metrics?.total_bookings ?? "—",
      description: "Platform bookings",
    },
  ];

  const adminAreas = [
    {
      title: "Users",
      description:
        "View and manage farmer, Service Provider, and administrator accounts.",
      icon: "👥",
    },
    {
      title: "Provider verification",
      description:
        "Review provider profiles and documents before they become trusted providers.",
      icon: "✓",
      featured: true,
    },
    {
      title: "Services",
      description:
        "Manage agricultural service categories and marketplace offerings.",
      icon: "▦",
    },
    {
      title: "Bookings",
      description:
        "Monitor platform bookings, statuses, and service activity.",
      icon: "▣",
    },
    {
      title: "Disputes",
      description:
        "Review customer and Service Provider disputes and track their resolution.",
      icon: "⚖",
    },
    {
      title: "Documents",
      description:
        "Review Service Provider verification documents and platform records.",
      icon: "▤",
    },
  ];

  const loadProviderQueue = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_URL}/admin/provider-verification`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await response.json();

      if (!response.ok || !Array.isArray(data)) {
        throw new Error(
          data.detail || "Could not load providers for verification."
        );
      }

      setProviderQueue(data);
      setQueueError("");
    } catch (requestError) {
      console.error("Provider verification queue error:", requestError);
      setProviderQueue([]);
      setQueueError(
        requestError.message ||
          "Could not load providers for verification."
      );
    } finally {
      setQueueLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadProviderQueue();
  }, [loadProviderQueue]);

  async function loadProviderDetail(providerId) {
    setSelectedProviderId(providerId);
    setDetailLoading(true);
    setDetailError("");
    setVerificationMessage({ type: "", text: "" });

    try {
      const response = await fetch(
        `${API_URL}/admin/provider-verification/${providerId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not load this provider for review."
        );
      }

      setProviderDetail(data);
    } catch (requestError) {
      console.error("Provider verification detail error:", requestError);
      setProviderDetail(null);
      setDetailError(
        requestError.message ||
          "Could not load this provider for review."
      );
    } finally {
      setDetailLoading(false);
    }
  }

  async function updateDocumentStatus(documentId, action) {
    const actionLabel =
      action === "verify" ? "verified" : "rejected";

    setVerificationAction(`document-${documentId}`);
    setVerificationMessage({ type: "", text: "" });

    try {
      const response = await fetch(
        `${API_URL}/admin/documents/${documentId}/${action}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || `Document could not be ${actionLabel}.`
        );
      }

      await loadProviderDetail(selectedProviderId);
      await loadProviderQueue();
      setVerificationMessage({
        type: "success",
        text: `Document ${actionLabel} successfully.`,
      });
    } catch (requestError) {
      console.error("Document verification action error:", requestError);
      setVerificationMessage({
        type: "error",
        text:
          requestError.message ||
          `Document could not be ${actionLabel}.`,
      });
    } finally {
      setVerificationAction("");
    }
  }

  async function verifySelectedProvider() {
    if (!selectedProviderId) {
      return;
    }

    setVerificationAction("provider");
    setVerificationMessage({ type: "", text: "" });

    try {
      const response = await fetch(
        `${API_URL}/admin/provider-verification/${selectedProviderId}/verify`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Provider could not be verified."
        );
      }

      await loadProviderDetail(selectedProviderId);
      await loadProviderQueue();
      setVerificationMessage({
        type: "success",
        text: "Provider verified successfully.",
      });
    } catch (requestError) {
      console.error("Provider verification action error:", requestError);
      setVerificationMessage({
        type: "error",
        text:
          requestError.message || "Provider could not be verified.",
      });
    } finally {
      setVerificationAction("");
    }
  }

  async function openUploadedDocument(document) {
    try {
      const response = await fetch(
        `${API_URL}/provider/documents/${document.document_id}/file`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Document file could not be opened.");
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      window.open(objectUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (requestError) {
      setVerificationMessage({ type: "error", text: requestError.message || "Document file could not be opened." });
    }
  }

  return (
    <main className="admin-page">
      {onOfficerApplications && <button className="primary-button" type="button" onClick={onOfficerApplications}>Field Officer Applications</button>}
      {onManageFieldWork && <button className="primary-button" type="button" onClick={onManageFieldWork}>Manage Field Work</button>}
      {onManageCatalogue && <button className="primary-button" type="button" onClick={onManageCatalogue}>Crop & Input Catalogue</button>}
      {onManageSops && <button className="primary-button" type="button" onClick={onManageSops}>Manage Crop SOPs</button>}
      <header className="admin-topbar">
        <button
          className="admin-back-button"
          onClick={onBack}
          type="button"
        >
          ← Marketplace
        </button>

        <div className="admin-brand">
          <p className="admin-brand-eyebrow">
            Platform administration
          </p>

          <h1>AgriConnect Admin</h1>
        </div>

        <div className="admin-account">
          <span className="admin-user-name">
            Hi, {user?.full_name || "Admin"}
          </span>

          {logoutAction}
        </div>
      </header>

      <div className="admin-content">
        <section className="admin-hero">
          <p className="admin-eyebrow">
            Admin dashboard
          </p>

          <h2>
            Manage the AgriConnect platform.
          </h2>

          <p className="admin-hero-text">
            Monitor platform activity, manage users and Service Providers,
            oversee services and bookings, and maintain a trusted
            agricultural services marketplace.
          </p>
        </section>

        <section className="admin-metrics">
          {dashboardMetrics.map((metric) => (
            <article
              className="admin-metric-card"
              key={metric.label}
            >
              <p className="admin-metric-label">
                {metric.label}
              </p>

              <strong className="admin-metric-value">
                {loading ? "..." : metric.value}
              </strong>

              <p className="admin-metric-description">
                {metric.description}
              </p>
            </article>
          ))}
        </section>

        {error && (
          <section className="admin-error">
            <strong>Could not load dashboard data.</strong>
            <span>{error}</span>
          </section>
        )}

        <section className="admin-management">
          <div className="admin-section-heading">
            <div>
              <p className="admin-eyebrow">
                Platform controls
              </p>

              <h2>
                Administration
              </h2>
            </div>

            <p>
              Core tools for operating AgriConnect.
            </p>
          </div>

          <div className="admin-area-grid">
            {adminAreas.map((area) => (
              <article
                className={`admin-area-card ${
                  area.featured
                    ? "admin-area-card-featured"
                    : ""
                }`}
                key={area.title}
              >
                <div className="admin-area-icon">
                  {area.icon}
                </div>

                <div className="admin-area-content">
                  <div className="admin-area-title-row">
                    <h3>{area.title}</h3>

                    {area.featured && (
                      <span className="admin-featured-tag">
                        Priority
                      </span>
                    )}
                  </div>

                  <p>
                    {area.description}
                  </p>

                  <button
                    className={
                      area.featured
                        ? "admin-area-button admin-area-button-primary"
                        : "admin-area-button"
                    }
                    type="button"
                    disabled={!area.featured}
                    onClick={
                      area.featured
                        ? () =>
                            document
                              .getElementById("provider-verification")
                              ?.scrollIntoView({ behavior: "smooth" })
                        : undefined
                    }
                    title={
                      area.featured
                        ? "Review provider verification requests"
                        : "This administration module will be enabled as its backend capability is implemented."
                    }
                  >
                    {area.featured ? "Review providers" : "Coming next"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section
          className="admin-provider-verification"
          id="provider-verification"
        >
          <div className="admin-section-heading">
            <div>
              <p className="admin-eyebrow">
                Provider validation
              </p>

              <h2>
                Provider verification
              </h2>
            </div>

            <p>
              Review documents before verifying a provider.
            </p>
          </div>

          <div className="admin-provider-review-layout">
            <section className="admin-provider-queue">
              <h3>Providers awaiting review</h3>

              {queueLoading ? (
                <p className="admin-provider-loading">
                  Loading providers...
                </p>
              ) : queueError ? (
                <p className="admin-provider-error">
                  {queueError}
                </p>
              ) : providerQueue.length === 0 ? (
                <div className="admin-provider-empty-state">
                  <strong>No providers require review.</strong>
                  <p>
                    Providers with unverified profiles will appear here.
                  </p>
                </div>
              ) : (
                <div className="admin-provider-queue-list">
                  {providerQueue.map((provider) => (
                    <button
                      className={`admin-provider-queue-card ${
                        selectedProviderId === provider.provider_id
                          ? "admin-provider-queue-card-selected"
                          : ""
                      }`}
                      key={provider.provider_id}
                      onClick={() =>
                        loadProviderDetail(provider.provider_id)
                      }
                      type="button"
                    >
                      <div className="admin-provider-queue-card-header">
                        <div>
                          <strong>
                            {provider.business_name ||
                              provider.provider_name}
                          </strong>
                          <span>
                            Provider ID: {provider.provider_id}
                          </span>
                        </div>

                        <span className="admin-provider-status admin-provider-status-pending">
                          Awaiting verification
                        </span>
                      </div>

                      <div className="admin-provider-document-counts">
                        <span>
                          {provider.submitted_document_count} submitted
                        </span>
                        <span>
                          {provider.verified_document_count} verified
                        </span>
                        <span>
                          {provider.pending_document_count} pending
                        </span>
                        <span>
                          {provider.rejected_document_count} rejected
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="admin-provider-detail">
              <h3>Provider review</h3>

              {!selectedProviderId ? (
                <div className="admin-provider-empty-state">
                  <strong>Select a provider to review.</strong>
                  <p>
                    Review provider documents and verify the provider
                    when eligible.
                  </p>
                </div>
              ) : detailLoading ? (
                <p className="admin-provider-loading">
                  Loading provider details...
                </p>
              ) : detailError ? (
                <p className="admin-provider-error">
                  {detailError}
                </p>
              ) : providerDetail ? (
                <>
                  <div className="admin-provider-profile">
                    <div>
                      <p className="admin-provider-profile-label">
                        Provider
                      </p>
                      <h4>
                        {providerDetail.provider.business_name ||
                          providerDetail.provider.provider_name}
                      </h4>
                      <p>
                        Provider ID: {providerDetail.provider.provider_id}
                      </p>
                    </div>

                    <div className="admin-provider-profile-statuses">
                      <span
                        className={`admin-provider-status ${
                          providerDetail.provider.is_active
                            ? "admin-provider-status-active"
                            : "admin-provider-status-inactive"
                        }`}
                      >
                        {providerDetail.provider.is_active
                          ? "Active"
                          : "Inactive"}
                      </span>

                      <span
                        className={`admin-provider-status ${
                          providerDetail.provider.verified_at
                            ? "admin-provider-status-verified"
                            : "admin-provider-status-pending"
                        }`}
                      >
                        {providerDetail.provider.verified_at
                          ? "Verified"
                          : "Awaiting verification"}
                      </span>
                    </div>
                  </div>

                  {providerDetail.provider.description && (
                    <p className="admin-provider-description">
                      {providerDetail.provider.description}
                    </p>
                  )}

                  <div className="admin-provider-verify-action">
                    <div>
                      <strong>Verify this provider</strong>
                      <p>
                        At least one submitted document must be verified
                        before this provider can be verified.
                      </p>
                    </div>

                    <button
                      className="admin-verify-provider-button"
                      disabled={
                        verificationAction === "provider" ||
                        Boolean(providerDetail.provider.verified_at)
                      }
                      onClick={verifySelectedProvider}
                      type="button"
                    >
                      {verificationAction === "provider"
                        ? "Verifying..."
                        : providerDetail.provider.verified_at
                          ? "Provider verified"
                          : "Verify provider"}
                    </button>
                  </div>

                  {verificationMessage.text && (
                    <p
                      className={`admin-provider-action-message admin-provider-action-message-${verificationMessage.type}`}
                    >
                      {verificationMessage.text}
                    </p>
                  )}

                  <div className="admin-provider-document-list">
                    <h4>Submitted documents</h4>

                    {providerDetail.documents.length === 0 ? (
                      <div className="admin-provider-empty-state">
                        <strong>No documents submitted.</strong>
                        <p>
                          This provider cannot be verified until an admin
                          verifies at least one submitted document.
                        </p>
                      </div>
                    ) : (
                      providerDetail.documents.map((document) => (
                        <article
                          className="admin-provider-document-card"
                          key={document.document_id}
                        >
                          <div className="admin-provider-document-header">
                            <div>
                              <h5>
                                {document.document_type_label ||
                                  document.document_type}
                              </h5>
                              <p>{document.file_name}</p>
                            </div>

                            <span
                              className={`admin-provider-status admin-provider-status-${document.verification_status}`}
                            >
                              {document.verification_status}
                            </span>
                          </div>

                          {document.has_uploaded_file ? (
                            <button className="admin-document-reject-button" onClick={() => openUploadedDocument(document)} type="button">Open uploaded file</button>
                          ) : (
                            <p className="admin-provider-document-reference"><strong>Document reference:</strong>{" "}{document.file_url}</p>
                          )}

                          {document.verification_status === "pending" && (
                            <div className="admin-provider-document-actions">
                              <button
                                className="admin-document-verify-button"
                                disabled={
                                  verificationAction ===
                                  `document-${document.document_id}`
                                }
                                onClick={() =>
                                  updateDocumentStatus(
                                    document.document_id,
                                    "verify"
                                  )
                                }
                                type="button"
                              >
                                Verify document
                              </button>

                              <button
                                className="admin-document-reject-button"
                                disabled={
                                  verificationAction ===
                                  `document-${document.document_id}`
                                }
                                onClick={() =>
                                  updateDocumentStatus(
                                    document.document_id,
                                    "reject"
                                  )
                                }
                                type="button"
                              >
                                Reject document
                              </button>
                            </div>
                          )}
                        </article>
                      ))
                    )}
                  </div>
                </>
              ) : null}
            </section>
          </div>
        </section>

        <section className="admin-info-card">
          <div>
            <p className="admin-eyebrow">
              Platform principle
            </p>

            <h2>
              Trust first. Scale second.
            </h2>
          </div>

          <p>
            Service Provider verification, reliable booking workflows,
            transparent service information, and proper platform
            records are the foundation for a production-ready
            AgriConnect marketplace.
          </p>
        </section>
      </div>

      <footer className="admin-footer">
        © 2026 AgriConnect · Platform administration
      </footer>
    </main>
  );
}

export default AdminDashboard;
