import HomeFeed from "./HomeFeed";
import "./SocialShell.css";

function SocialShell({ user }) {
  return (
    <div className="social-shell">
      <header className="social-topbar">
        <div className="social-brand">AgriConnect</div>

        <button
          className="notification-button"
          type="button"
          aria-label="Notifications"
        >
          🔔
        </button>
      </header>

      <main className="social-content">
        <HomeFeed />
      </main>

      <nav className="social-bottom-nav" aria-label="Main navigation">
        <button className="social-nav-item active" type="button">
          <span>⌂</span>
          <small>Home</small>
        </button>

        <button className="social-nav-item" type="button">
          <span>⌕</span>
          <small>Explore</small>
        </button>

        <button
          className="social-create-button"
          type="button"
          aria-label="Create"
        >
          +
        </button>

        <button className="social-nav-item" type="button">
          <span>🌱</span>
          <small>My Farm</small>
        </button>

        <button className="social-nav-item" type="button">
          <span>○</span>
          <small>You</small>
        </button>
      </nav>
    </div>
  );
}

export default SocialShell;