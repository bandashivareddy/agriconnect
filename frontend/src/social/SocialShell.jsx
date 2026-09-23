import { useState } from "react";
import HomeFeed from "./HomeFeed";
import Explore from "./Explore";
import CreatePost from "./CreatePost";
import PersonProfile from "./PersonProfile";
import FarmProfile from "./FarmProfile";
import { SocialPeopleContext } from "./SocialPeopleContext";
import { people, farms, notifications as mockNotifications } from "./mockSocialData";
import "./SocialShell.css";

function SocialShell({ user }) {
  const [section, setSection] = useState("home");
  const [creating, setCreating] = useState(false);
  const [notifications, setNotifications] = useState(mockNotifications);
  const [conversationTarget, setConversationTarget] = useState(null);
  const [followedPersonIds, setFollowedPersonIds] = useState(["ramesh"]);
  const [followedFarmIds, setFollowedFarmIds] = useState([]);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [selectedFarm, setSelectedFarm] = useState(null);
  const [feedTab, setFeedTab] = useState("for-you");
  const [sessionPosts, setSessionPosts] = useState([]);

  function addPost(post) {
    setSessionPosts((current) => [post, ...current]);
    setCreating(false);
    setSelectedPerson(null);
    setSelectedFarm(null);
    setConversationTarget(null);
    setFeedTab("for-you");
    setSection("home");
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function toggleFollow(personId) {
    setFollowedPersonIds((ids) => ids.includes(personId)
      ? ids.filter((id) => id !== personId)
      : [...ids, personId]);
  }

  function toggleFarmFollow(farmId) {
    setFollowedFarmIds((ids) => ids.includes(farmId)
      ? ids.filter((id) => id !== farmId)
      : [...ids, farmId]);
  }

  function openPerson(personId) {
    const person = people.find((entry) => entry.id === personId);
    if (person) {
      setSelectedFarm(null);
      setSelectedPerson(person);
    }
  }

  function openFarm(farmId) {
    const farm = farms.find((entry) => entry.id === farmId);
    if (farm) setSelectedFarm(farm);
  }
  const unreadCount = notifications.filter((item) => !item.read).length;

  function openNotifications() {
    setSelectedFarm(null);
    setSelectedPerson(null);
    setSection("notifications");
    setNotifications((items) => items.map((item) => ({ ...item, read: true })));
  }

  return (
    <SocialPeopleContext.Provider value={{ followedPersonIds, toggleFollow, openPerson, followedFarmIds, toggleFarmFollow, openFarm }}>
    <div className="social-shell">
      <header className="social-topbar">
        <div className="social-brand">AgriConnect</div>

        <button
          className="notification-button"
          type="button"
          aria-label={unreadCount ? `Notifications, ${unreadCount} unread` : "Notifications"}
          onClick={openNotifications}
        >
          🔔
          {unreadCount > 0 && <span className="social-unread-dot" aria-hidden="true" />}
        </button>
      </header>

      <main className="social-content">
        <div hidden={section !== "home" || Boolean(selectedPerson || selectedFarm)}>
          <HomeFeed sessionPosts={sessionPosts} conversationTarget={conversationTarget} feedTab={feedTab} onChangeTab={setFeedTab} />
        </div>
        {section === "explore" && <div hidden={Boolean(selectedPerson || selectedFarm)}><Explore /></div>}
        {selectedPerson && !selectedFarm && (
          <PersonProfile person={selectedPerson} following={followedPersonIds.includes(selectedPerson.id)} onToggleFollow={() => toggleFollow(selectedPerson.id)} onBack={() => setSelectedPerson(null)} backLabel="Back" />
        )}
        {selectedFarm && (
          <FarmProfile farm={selectedFarm} following={followedFarmIds.includes(selectedFarm.id)} onToggleFollow={() => toggleFarmFollow(selectedFarm.id)} onBack={() => setSelectedFarm(null)} backLabel="Back" />
        )}
        {section === "notifications" && !selectedPerson && !selectedFarm && (
          <section className="social-notifications" aria-labelledby="social-notifications-title">
            <h1 id="social-notifications-title">Notifications</h1>
            <ul>
              {notifications.map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => {
                    setConversationTarget({ postId: item.postId, commentId: item.commentId });
                    setFeedTab("for-you");
                    setSection("home");
                  }}>
                    <span className="social-notification-avatar" aria-hidden="true">{item.author.slice(0, 1)}</span>
                    <span className="social-notification-copy">
                      <span className="social-notification-action"><strong>{item.author}</strong> {item.type === "reply" ? "replied to your comment" : "commented on your post"}</span>
                      <span className="social-notification-excerpt">“{item.text}”</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>

      <nav className="social-bottom-nav" aria-label="Main navigation">
        <button
          className={`social-nav-item ${section === "home" ? "active" : ""}`}
          type="button"
          onClick={() => { setSelectedFarm(null); setSelectedPerson(null); setSection("home"); }}
        >
          <span>⌂</span>
          <small>Home</small>
        </button>

        <button
          className={`social-nav-item ${section === "explore" ? "active" : ""}`}
          type="button"
          onClick={() => { setSelectedFarm(null); setSelectedPerson(null); setSection("explore"); }}
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
      {creating && <CreatePost user={user} onPost={addPost} onClose={() => setCreating(false)} />}
    </div>
    </SocialPeopleContext.Provider>
  );
}

export default SocialShell;
