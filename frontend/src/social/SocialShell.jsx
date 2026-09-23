import { useState } from "react";
import HomeFeed from "./HomeFeed";
import Explore from "./Explore";
import CreatePost from "./CreatePost";
import "./SocialShell.css";

function SocialShell({ user }) {
  const [section, setSection] = useState("home");
  const [creating, setCreating] = useState(false);

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
        {section === "home" && <HomeFeed />}
        {section === "explore" && <Explore />}
      </main>

      <nav className="social-bottom-nav" aria-label="Main navigation">
        <button
          className={`social-nav-item ${section === "home" ? "active" : ""}`}
          type="button"
          onClick={() => setSection("home")}
        >
          <span>⌂</span>
          <small>Home</small>
        </button>

        <button
          className={`social-nav-item ${section === "explore" ? "active" : ""}`}
          type="button"
          onClick={() => setSection("explore")}
        >
          <span>⌕</span>
          <small>Explore</small>
        </button>

        <button
          className="social-create-button"
          type="button"
          aria-label="Create"
          onClick={() => setCreating(true)}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
            <path d="m15 5 4 4M4 20l4-1L20 7a2.83 2.83 0 0 0-4-4L4 15l-1 6Z" />
          </svg>
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
      {creating && <CreatePost onClose={() => setCreating(false)} />}
    </div>
  );
}

export default SocialShell;
