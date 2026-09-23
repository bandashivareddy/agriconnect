import { useTranslation } from "react-i18next";
import { t, messageText } from "./i18n";
import { useCallback, useEffect, useState } from "react";
import "./App.css";
import BookingForm from "./BookingForm";
import MyBookings from "./MyBookings";
import AuthPage from "./AuthPage";
import Onboarding from "./Onboarding";
import OfficerApplication, { AdminOfficerApplications } from "./OfficerApplications";
import FarmSetup from "./FarmSetup";
import SupplierDashboard from "./SupplierDashboard";
import SupplierEquipment from "./SupplierEquipment";
import SupplierAvailability from "./SupplierAvailability";
import Notifications from "./Notifications";
import AdminDashboard from "./AdminDashboard";
import FarmCatalogueAdmin from "./FarmCatalogueAdmin";
import CropManagement from "./CropManagement";
import SopManagement from "./SopManagement";
import FieldWork from "./FieldWork";
import FieldWorkAdmin from "./FieldWorkAdmin";
import MyServices from "./MyServices";
import ProviderProfile from "./ProviderProfile";
import ProviderVerification from "./ProviderVerification";
import { API_BASE_URL } from "./api";
import SocialShell from "./social/SocialShell";
import FarmerWorkspace from "./FarmerWorkspace";

const API_URL = API_BASE_URL;

function SignOutAction({ onSignOut }) {
  useTranslation();
  return (
    <button
      aria-label={t("Sign out")}
      className="sign-out-action"
      onClick={onSignOut}
      title={t("Sign out")}
      type="button"
    >
      <span aria-hidden="true" className="sign-out-icon">
        ⇥
      </span>
      <span className="sign-out-label">{t("Sign out")}</span>
    </button>
  );
}

function AuthenticatedPage({ children, onSignOut, showAccountAction = true }) {
  useTranslation();
  return (
    <div className="authenticated-page-shell">
      {showAccountAction && <div className="authenticated-page-account">
          <SignOutAction onSignOut={onSignOut} />
        </div>}
      {children}
    </div>
  );
}

function App() {
  useTranslation();
  /*
   * =====================================================
   * Fresh launcher start
   * =====================================================
   *
   * When AgriConnect is launched through the BAT file,
   * it opens with ?fresh_start=1.
   *
   * This clears any previous browser session so the
   * application starts at the login screen.
   *
   * Normal visits to http://localhost:5173 do NOT clear
   * the existing session.
   */

  const freshStart =
    new URLSearchParams(window.location.search).get("fresh_start") === "1";

  /*
   * =====================================================
   * Application state
   * =====================================================
   */

  const [setupToken, setSetupToken] = useState(null);
  const [services, setServices] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cropEntry, setCropEntry] = useState(null);
  const [fromMyFarm, setFromMyFarm] = useState(false);
  const [workspaceFarmId, setWorkspaceFarmId] = useState(null);
  const [cropCreateContext, setCropCreateContext] = useState(null);
  const [pendingSocialContext, setPendingSocialContext] = useState(null);
  const [selectedService, setSelectedService] = useState(null);
  const [page, setPage] = useState(() => {
  const token = localStorage.getItem("access_token");

  if (!token) {
    return "marketplace";
  }

  try {
    JSON.parse(localStorage.getItem("current_user"));
    return "home";
  } catch {
    return "marketplace";
  }
});

  const [adminMetrics, setAdminMetrics] = useState(null);
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState("");

  /*
   * =====================================================
   * Authentication
   * =====================================================
   *
   * A launcher start intentionally clears the previous
   * browser session.
   *
   * Normal application visits retain the existing session.
   */

  const [auth, setAuth] = useState(() => {
    if (freshStart) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("current_user");

      return null;
    }

    const token = localStorage.getItem("access_token");
    const savedUser = localStorage.getItem("current_user");

    return token && savedUser
      ? {
          token,
          user: JSON.parse(savedUser),
        }
      : null;
  });

  /*
   * Remove the launcher query parameter after the
   * initial session reset.
   */

  useEffect(() => {
    if (freshStart) {
      window.history.replaceState(
        {},
        document.title,
        window.location.pathname
      );
    }
  }, [freshStart]);

  /*
   * =====================================================
   * Capability helpers
   * =====================================================
   *
   * Capabilities are now the primary way we determine
   * what a user can do.
   *
   * Existing user_role is intentionally retained as a
   * backward-compatible fallback.
   */

  const capabilities = auth?.user?.capabilities || [];

  const isFieldOfficer = capabilities.includes("field_officer");

  const isFarmer =
    capabilities.includes("farmer") ||
    auth?.user?.user_role === "farmer";

  const isProvider =
    capabilities.includes("provider") ||
    auth?.user?.user_role === "supplier";

  const isAdmin =
    capabilities.includes("admin") ||
    auth?.user?.user_role === "admin";

  /*
   * =====================================================
   * Load marketplace services
   * =====================================================
   */

  useEffect(() => {
    fetch(`${API_URL}/services`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Could not load services.");
        }

        return response.json();
      })
      .then((data) => setServices(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  /*
   * =====================================================
   * Load admin dashboard
   * =====================================================
   */

  useEffect(() => {
    if (!auth?.token || !isAdmin || page !== "admin") {
      return;
    }

    setAdminLoading(true);
    setAdminError("");

    fetch(`${API_URL}/admin/dashboard`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${auth.token}`,
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            `Could not load admin dashboard (${response.status}).`
          );
        }

        return response.json();
      })
      .then((data) => {
        console.log("Admin dashboard response:", data);
        setAdminMetrics(data);
      })
      .catch((err) => {
        console.error("Admin dashboard error:", err);
        setAdminError(err.message);
      })
      .finally(() => {
        setAdminLoading(false);
      });
  }, [auth, isAdmin, page]);

  /*
   * =====================================================
   * Capability protection / page correction
   * =====================================================
   */

  useEffect(() => {
    if (!auth) {
      return;
    }

    if (
      (page === "bookings" || page === "setup") &&
      !isFarmer
    ) {
      setPage("marketplace");
      setSelectedService(null);
      return;
    }

    if (
      (page === "supplier" ||
        page === "provider-services" ||
        page === "provider-profile" ||
        page === "provider-verification" ||
        page === "availability" ||
        page === "equipment") &&
      !isProvider
    ) {
      setPage("marketplace");
      setSelectedService(null);
      return;
    }

    if (page === "admin" && !isAdmin) {
      setPage("marketplace");
      setSelectedService(null);
    }
  }, [
    auth,
    page,
    isFarmer,
    isProvider,
    isAdmin,
  ]);

  /*
   * =====================================================
   * Search
   * =====================================================
   */

  const visibleServices = services.filter((service) => {
    const searchText =
      `${service.service_name} ${service.category_name} ${service.supplier_name}`
        .toLowerCase();

    return searchText.includes(search.toLowerCase());
  });

  /*
   * =====================================================
   * Login
   * =====================================================
   */

  function handleLogin(token, user) {
    localStorage.setItem("access_token", token);

    localStorage.setItem(
      "current_user",
      JSON.stringify(user)
    );

    setAuth({
      token,
      user,
    });

    setSelectedService(null);

    const userCapabilities = user.capabilities || [];
    const userIsAdmin =
      userCapabilities.includes("admin") || user.user_role === "admin";

    if (userIsAdmin) {
      setPage("admin");
    } else {
      setPage("home");
    }
  }

  /*
   * =====================================================
   * Logout
   * =====================================================
   */

  function handleLogout() {
    setFromMyFarm(false);
    setWorkspaceFarmId(null);
    setPendingSocialContext(null);
    setCropEntry(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");

    setSetupToken(null);
    setAuth(null);
    setSelectedService(null);
    setPage("auth");
  }

  /*
   * =====================================================
   * Farmer booking
   * =====================================================
   */

  function handleBookService(service) {
    if (!auth) {
      setPage("auth");
      return;
    }

    if (!isFarmer) {
      return;
    }

    setSelectedService(service);
  }

  /*
   * =====================================================
   * Navigation helpers
   * =====================================================
   */

  function goToMarketplace() {
    setFromMyFarm(false);
    setSelectedService(null);
    setPage("marketplace");
  }

  function goToSupplierDashboard() {
    if (!isProvider) {
      return;
    }

    setSelectedService(null);
    setPage("supplier");
  }

  function goToMyServices() {
    if (!isProvider) return;
    setSelectedService(null);
    setPage("provider-services");
  }

  function goToProviderProfile() {
    if (!isProvider) return;
    setSelectedService(null);
    setPage("provider-profile");
  }

  function goToProviderRegistration() {
    if (!isFarmer || isProvider) return;
    setSelectedService(null);
    setPage("provider-registration");
  }

  const handleSetupComplete = useCallback((user, providerRegistration = false) => {
    localStorage.setItem("current_user", JSON.stringify(user));
    setAuth({ ...auth, user });
    setSetupToken(auth.token);
    if (providerRegistration) setPage("supplier");
  }, [auth]);

  const completeProviderRegistration = useCallback((user) => {
    handleSetupComplete(user, true);
  }, [handleSetupComplete]);

  function goToProviderVerification() {
    if (!isProvider) return;
    setSelectedService(null);
    setPage("provider-verification");
  }

  function goToAvailability() {
    if (!isProvider) {
      return;
    }

    setSelectedService(null);
    setPage("availability");
  }

  function goToEquipment() {
    if (!isProvider) {
      return;
    }

    setSelectedService(null);
    setPage("equipment");
  }

  function goToBookings() {
    if (!isFarmer) {
      return;
    }

    setSelectedService(null);
    setPage("bookings");
  }

  function goToMyFarm() {
    if (!isFarmer) return;
    setSelectedService(null);
    setFromMyFarm(true);
    setPage("my-farm");
  }

  function goToFarmSetup() {
    if (!isFarmer) {
      return;
    }

    setSelectedService(null);
    setPage("setup");
  }

  function goToAdminDashboard() {
    if (!isAdmin) {
      return;
    }

    setSelectedService(null);
    setPage("admin");
  }

  /*
   * =====================================================
   * Authentication page
   * =====================================================
   */

  async function refreshOfficerAccess() {
    const response = await fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${auth.token}` } });
    if (!response.ok) throw new Error("Could not refresh your account. Please sign in again.");
    const user = await response.json();
    if (!user.capabilities.includes("field_officer")) throw new Error("Field Officer access is not currently enabled. Contact your administrator.");
    localStorage.setItem("current_user", JSON.stringify(user));
    setAuth({ ...auth, user });
    setPage("field-work");
  }

  const applicantOnly = auth?.user.signup_intent === "field_officer" && !isFieldOfficer && !isFarmer && !isProvider && !isAdmin;
  if (auth && (page === "officer-application" || applicantOnly)) {
    return <AuthenticatedPage onSignOut={handleLogout}><OfficerApplication token={auth.token} user={auth.user} onBack={applicantOnly ? undefined : goToMarketplace} onApproved={refreshOfficerAccess} /></AuthenticatedPage>;
  }
  if (auth?.user.signup_intent === "landowner" && !isFarmer && !isProvider && !isFieldOfficer && !isAdmin) {
    return <AuthenticatedPage onSignOut={handleLogout}><main className="cm-page"><section className="cm-card cm-content"><h1>{t("Managed farming coming later")}</h1><p>{t("Your AgriConnect account is ready. Managed farming for landowners is not available yet. You can sign in here again using the same mobile number or email.")}</p></section></main></AuthenticatedPage>;
  }

  // Field work is independent of optional farmer/provider setup on the same account.
  // Existing onboarding remains enforced when returning to those workflows.
  if (page === "field-work" && auth && isFieldOfficer) {
    return <AuthenticatedPage onSignOut={handleLogout}><FieldWork token={auth.token} onBack={goToMarketplace} /></AuthenticatedPage>;
  }

  if (auth && 
    page !== "home" &&
    setupToken !== auth.token) {
    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <Onboarding token={auth.token} onComplete={handleSetupComplete} onBack={handleLogout} />
      </AuthenticatedPage>
    );
  }

  if (page === "auth") {
    return (
      <AuthPage
        onLogin={handleLogin}
        onBack={goToMarketplace}
      />
    );
  }

  /*
   * =====================================================
   * Admin dashboard
   * =====================================================
   */

  if (page === "home") {
  if (!auth) {
    return null;
  }

  return (
    <SocialShell
      user={auth.user}
      operationalWorkspace={isFieldOfficer
        ? { label: "Field Work", icon: "📋", onOpen: () => { setSelectedService(null); setPage("field-work"); } }
        : isFarmer
          ? { label: "My Farm", icon: "🌱", onOpen: goToMyFarm }
          : isProvider
            ? { label: "My Services", icon: "🚜", onOpen: goToSupplierDashboard }
            : undefined}
      initialComposerContext={pendingSocialContext}
      onComposerConsumed={() => setPendingSocialContext(null)}
    />
  );
}
  if (page === "my-farm") {
    if (!auth || !isFarmer) return null;
    return <AuthenticatedPage onSignOut={handleLogout}><FarmerWorkspace token={auth.token} selectedFarmId={workspaceFarmId} onSelectFarm={setWorkspaceFarmId} onBack={() => setPage("home")} onManageFarm={goToFarmSetup} onOpenCrop={(id) => { setCropEntry(id); setCropCreateContext(null); setPage("crop-cycles"); }} /></AuthenticatedPage>;
  }
  if (page === "crop-cycles") {
    if (!auth || !isFarmer) return null;
    return <AuthenticatedPage onSignOut={handleLogout}><CropManagement onShareUpdate={(context) => { setPendingSocialContext(context); setPage("home"); }} farmerId={auth.user.user_id} initialCycleId={cropEntry} initialContext={cropCreateContext} onContextConsumed={() => setCropCreateContext(null)} token={auth.token} backLabel={fromMyFarm ? "My Farm" : "Marketplace"} onBack={fromMyFarm ? goToMyFarm : goToMarketplace} onFarms={goToFarmSetup} /></AuthenticatedPage>;
  }

  if (page === "officer-applications" && auth && isAdmin) {
    return <AuthenticatedPage onSignOut={handleLogout}><AdminOfficerApplications token={auth.token} onBack={goToAdminDashboard} onAssignments={() => setPage("field-operations")} /></AuthenticatedPage>;
  }

  if (page === "field-operations") {
    if (!auth || !isAdmin) return null;
    return <AuthenticatedPage onSignOut={handleLogout}><FieldWorkAdmin token={auth.token} onBack={goToAdminDashboard} /></AuthenticatedPage>;
  }

  if (page === "farm-catalogue") {
    if (!auth || !isAdmin) return null;
    return <AuthenticatedPage onSignOut={handleLogout}><FarmCatalogueAdmin token={auth.token} onBack={goToAdminDashboard} /></AuthenticatedPage>;
  }

  if (page === "crop-sops") {
    if (!auth || !isAdmin) return null;
    return <AuthenticatedPage onSignOut={handleLogout}><SopManagement token={auth.token} onBack={goToAdminDashboard} /></AuthenticatedPage>;
  }

  if (page === "admin") {
    if (!auth || !isAdmin) {
      return null;
    }

    return (
      <AuthenticatedPage onSignOut={handleLogout} showAccountAction={false}>
        <AdminDashboard
          user={auth.user}
          token={auth.token}
          metrics={adminMetrics}
          loading={adminLoading}
          error={adminError}
          onBack={goToMarketplace}
          onManageSops={() => setPage("crop-sops")}
          onManageFieldWork={() => setPage("field-operations")}
          onOfficerApplications={() => setPage("officer-applications")}
          onManageCatalogue={() => setPage("farm-catalogue")}
          logoutAction={<SignOutAction onSignOut={handleLogout} />}
        />
      </AuthenticatedPage>
    );
  }

  /*
   * =====================================================
   * Farmer-only pages
   * =====================================================
   */

  if (page === "setup") {
    if (!auth || !isFarmer) {
      return null;
    }

    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <FarmSetup
          token={auth.token}
          onBack={fromMyFarm ? goToMyFarm : goToMarketplace}
          onStartCrop={(context) => { setCropEntry(null); setCropCreateContext(context); setPage("crop-cycles"); }}
        />
      </AuthenticatedPage>
    );
  }

  /*
   * =====================================================
   * Farmer bookings
   * =====================================================
   */

  if (page === "bookings") {
    if (!auth || !isFarmer) {
      return null;
    }

    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <MyBookings
          onOpenCrop={(id) => { setCropEntry(id); setPage("crop-cycles"); }}
          farmerId={auth.user.user_id}
          token={auth.token}
          onBack={goToMarketplace}
        />
      </AuthenticatedPage>
    );
  }

  /*
   * =====================================================
   * Provider availability
   * =====================================================
   */

  if (page === "availability") {
    if (!auth || !isProvider) {
      return null;
    }

    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <SupplierAvailability
          token={auth.token}
          onBack={goToSupplierDashboard}
        />
      </AuthenticatedPage>
    );
  }

  /*
   * =====================================================
   * Provider equipment
   * =====================================================
   */

  if (page === "equipment") {
    if (!auth || !isProvider) {
      return null;
    }

    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <SupplierEquipment
          token={auth.token}
          onBack={goToSupplierDashboard}
        />
      </AuthenticatedPage>
    );
  }

  /*
   * =====================================================
   * Provider dashboard
   * =====================================================
   */

  if (page === "supplier") {
    if (!auth || !isProvider) {
      return null;
    }

    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <SupplierDashboard
          token={auth.token}
          onBack={goToMarketplace}
          onManageServices={goToMyServices}
          onManageAvailability={goToAvailability}
          onManageEquipment={goToEquipment}
          onManageProfile={goToProviderProfile}
          onManageVerification={goToProviderVerification}
        />
      </AuthenticatedPage>
    );
  }

  if (page === "provider-services") {
    if (!auth || !isProvider) return null;
    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <MyServices token={auth.token} onBack={goToSupplierDashboard} />
      </AuthenticatedPage>
    );
  }

  if (page === "provider-registration") {
    if (!auth || !isFarmer || isProvider) return null;
    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <Onboarding
          token={auth.token}
          providerRegistration
          onComplete={completeProviderRegistration}
          onBack={goToMarketplace}
        />
      </AuthenticatedPage>
    );
  }

  if (page === "provider-profile") {
    if (!auth || !isProvider) return null;
    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <ProviderProfile token={auth.token} onBack={goToSupplierDashboard} />
      </AuthenticatedPage>
    );
  }

  if (page === "provider-verification") {
    if (!auth || !isProvider) return null;
    return (
      <AuthenticatedPage onSignOut={handleLogout}>
        <ProviderVerification token={auth.token} onBack={goToSupplierDashboard} />
      </AuthenticatedPage>
    );
  }

  /*
   * =====================================================
   * Marketplace
   * =====================================================
   */

  return (
    <div>
      {/* =================================================
          HEADER
          ================================================= */}

      <header className="site-header">
        <a className="brand" href="/">{t("AgriConnect")}</a>

        <nav className="main-nav">
          <div className="nav-links">
            <a href="#services">{t("Services")}</a>

            <a href="#how-it-works">{t("How it works")}</a>

            {/* -------------------------------------------
                FARMER NAVIGATION
                ------------------------------------------- */}

            {isFarmer && <>
                <button
                  className="login-button"
                  onClick={goToBookings}
                >{t("My bookings")}</button>

                <button
                  className="login-button"
                  onClick={goToFarmSetup}
                >{t("My Farms")}</button>
                <button className="login-button" onClick={() => { setSelectedService(null); setCropEntry(null); setPage("crop-cycles"); }}>{t("My Crops")}</button>
              </>}

            {/* -------------------------------------------
                PROVIDER NAVIGATION
                ------------------------------------------- */}

            {auth && !isFieldOfficer && !isAdmin && <button className="login-button" onClick={() => setPage("officer-application")}>{t("Apply as Field Officer")}</button>}
            {isFieldOfficer && <button className="login-button" onClick={() => setPage("field-work")}>{t("My Field Work")}</button>}

            {isFarmer && !isProvider && <button className="login-button" onClick={goToProviderRegistration}>{t("Become a Provider")}</button>}

            {isProvider && <button
                className="login-button"
                onClick={goToSupplierDashboard}
              >{t("Provider Dashboard")}</button>}

            {/* -------------------------------------------
                ADMIN NAVIGATION
                ------------------------------------------- */}

            {isAdmin && <button
                className="login-button"
                onClick={goToAdminDashboard}
              >{t("Admin dashboard")}</button>}
          </div>

          {/* =================================================
              ACCOUNT AREA
              ================================================= */}

          <div className="nav-account">
            {auth ? <>
                {isFarmer || isProvider ? <Notifications
                    token={auth.token}
                    userRole={auth.user.user_role}
                    onOpenBooking={(bookingContext) => {
                      if (bookingContext === "provider") {
                        goToSupplierDashboard();
                      } else if (bookingContext === "farmer") {
                        goToBookings();
                      }
                    }}
                  /> : null}

                <span className="signed-in-name">{t("Hi, ")}{auth.user.full_name}
                </span>

                <SignOutAction onSignOut={handleLogout} />
              </> : <button
                className="login-button"
                onClick={() => setPage("auth")}
              >{t("Sign in")}</button>}
          </div>
        </nav>
      </header>

      {/* =================================================
          SEARCH
          ================================================= */}

      <div className="marketplace-search">
        <div className="search-icon">
          ⌕
        </div>

        <input
          className="search-input"
          type="search"
          placeholder={t("Search services, categories, or service providers")}
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
        />
      </div>

      {/* =================================================
          MAIN MARKETPLACE
          ================================================= */}

      <main>
        {/* =================================================
            HERO
            ================================================= */}

        <section className="hero">
          <div className="hero-content">
            <p className="eyebrow">{t("Farming services, made simple")}</p>

            <h1>{t("Find the right help for every field.")}</h1>

            <p className="hero-text">{t("Discover trusted local agricultural services and equipment, compare prices, and book with confidence.")}</p>

            <a
              className="primary-button"
              href="#services"
            >{t("Browse services")}</a>
          </div>
        </section>

        {/* =================================================
            SERVICES
            ================================================= */}

        <section
          className="services-section"
          id="services"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">{t("Marketplace")}</p>

              <h2>{t("Available services")}</h2>
            </div>
          </div>

          {loading && <p className="status-message">{t("Loading services…")}</p>}

          {error && <p className="status-message error-message">
              {messageText(error)}{t(" Make sure the FastAPI server is running.")}</p>}

          {!loading &&
            !error &&
            visibleServices.length === 0 && <p className="status-message">{t("No services match your search.")}</p>}

          <div className="service-grid">
            {visibleServices.map((service) => (
              <article
                className="service-card"
                key={service.supplier_service_id}
              >
                <div className="service-card-top">
                  <span className="category-tag">
                    {service.category_name}
                  </span>

                  <span className="rating">
                    ★ {service.average_rating}
                  </span>
                </div>

                <h3>
                  {service.service_name}
                </h3>

                <p className="service-description">
                  {service.description || t("Agricultural service provided by a local Service Provider.")}
                </p>

                <div className="supplier">{t("Provided by")}{" "}
                  <strong>
                    {service.supplier_name}
                  </strong>
                </div>

                <div className="service-card-footer">
                  <div>
                    <span className="price">
                      ₹
                      {Number(
                        service.base_price
                      ).toLocaleString("en-IN")}
                    </span>

                    <span className="price-unit">
                      {" "}
                      / {service.pricing_unit}
                    </span>
                  </div>

                  {/* FARMER */}

                  {isFarmer && <button
                      className="book-button"
                      onClick={() =>
                        handleBookService(service)
                      }
                    >{t("Book now")}</button>}

                  {/* NOT LOGGED IN */}

                  {!auth && <button
                      className="book-button"
                      onClick={() =>
                        handleBookService(service)
                      }
                    >{t("Book now")}</button>}

                  {/* PROVIDER */}

                  {isProvider && <button
                      className="secondary-button"
                      onClick={goToSupplierDashboard}
                    >{t("Provider Dashboard")}</button>}

                  {/* ADMIN */}

                  {isAdmin && <button
                      className="secondary-button"
                      onClick={goToAdminDashboard}
                    >{t("Admin dashboard")}</button>}
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* =================================================
            BOOKING FORM
            Farmer capability
            ================================================= */}

        {selectedService && isFarmer && <BookingForm
            service={selectedService}
            token={auth.token}
            onBookingCreated={goToBookings}
            onClose={() =>
              setSelectedService(null)
            }
          />}

        {/* =================================================
            HOW IT WORKS
            ================================================= */}

        {!selectedService && <section
            className="how-it-works"
            id="how-it-works"
          >
            <p className="eyebrow">{t("How it works")}</p>

            <h2>{t("From search to service in three simple steps.")}</h2>

            <div className="steps">
              <div>
                <span>1</span>

                <h3>{t("Find a service")}</h3>

                <p>{t("Browse verified local Service Providers and compare offerings.")}</p>
              </div>

              <div>
                <span>2</span>

                <h3>{t("Book your slot")}</h3>

                <p>{t("Choose a suitable time, farm, and service requirement.")}</p>
              </div>

              <div>
                <span>3</span>

                <h3>{t("Get work done")}</h3>

                <p>{t("Track your booking and review the completed service.")}</p>
              </div>
            </div>
          </section>}
      </main>

      {/* =================================================
          FOOTER
          ================================================= */}

      <footer>{t("© 2026 AgriConnect · Built for better farming")}</footer>
    </div>
  );
}

export default App;
