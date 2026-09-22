import { useState } from "react";
import { posts } from "./mockSocialData";
import PostCard from "./PostCard";
import "./Explore.css";
import "./FarmProfile.css";

function FarmProfile({ farm, following, onToggleFollow, onBack }) {
  const [tab, setTab] = useState("updates");
  const updates = posts.filter((post) => farm.postIds.includes(post.id));

  return (
    <section className="farm-profile">
      <button className="explore-back" type="button" onClick={onBack}>
        ← Farms
      </button>
      <header className="farm-profile-header">
        <div className="farm-profile-avatar" aria-hidden="true">🌱</div>
        <h1>{farm.name}</h1>
        <p className="farm-profile-location">{farm.location}</p>
        <ul className="farm-profile-labels" aria-label="Farm crops">
          {farm.crops.map((crop) => <li key={crop}>{crop}</li>)}
        </ul>
        <p className="farm-profile-bio">{farm.bio}</p>
        <button
          className="farm-profile-follow"
          type="button"
          aria-label={`${following ? "Unfollow" : "Follow"} ${farm.name}`}
          aria-pressed={following}
          onClick={onToggleFollow}
        >
          {following ? "Following" : "Follow"}
        </button>
      </header>
      <div className="farm-profile-tabs" aria-label="Farm sections">
        <button type="button" aria-pressed={tab === "updates"} onClick={() => setTab("updates")}>
          Updates
        </button>
        <button type="button" aria-pressed={tab === "crops"} onClick={() => setTab("crops")}>
          Crops
        </button>
      </div>
      {tab === "updates" ? (
        <div className="farm-profile-updates" aria-label="Farm updates">
          {updates.map((post) => <PostCard key={post.id} post={post} />)}
        </div>
      ) : (
        <section className="farm-profile-crops">
          <h2>Growing at {farm.name}</h2>
          <p>A look at the crops you’ll see in our farm stories.</p>
          <ul>
            {farm.crops.map((crop) => <li key={crop}>{crop}</li>)}
          </ul>
        </section>
      )}
    </section>
  );
}

export default FarmProfile;
