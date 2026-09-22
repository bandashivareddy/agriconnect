import { useState } from "react";
import { farms } from "./mockSocialData";
import FarmProfile from "./FarmProfile";
import "./Explore.css";
import "./FarmsExplore.css";

function FarmsExplore({ onBack }) {
  const [query, setQuery] = useState("");
  const [selectedFarm, setSelectedFarm] = useState(null);
  const [following, setFollowing] = useState({});

  function toggleFollow(farmId) {
    setFollowing((current) => ({ ...current, [farmId]: !current[farmId] }));
  }

  if (selectedFarm) {
    return (
      <FarmProfile
        farm={selectedFarm}
        following={Boolean(following[selectedFarm.id])}
        onToggleFollow={() => toggleFollow(selectedFarm.id)}
        onBack={() => setSelectedFarm(null)}
      />
    );
  }

  const search = query.trim().toLowerCase();
  const visibleFarms = farms.filter((farm) =>
    [farm.name, farm.location, ...farm.crops].join(" ").toLowerCase().includes(search)
  );

  return (
    <section className="farms-explore">
      <button className="explore-back" type="button" onClick={onBack}>
        ← Explore
      </button>
      <div className="explore-header">
        <h1>Farms</h1>
        <p>Discover farms, see what’s growing and follow their stories.</p>
      </div>
      <label className="explore-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          placeholder="Search farms, places or crops..."
          aria-label="Search farms"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <ul className="farms-discovery-list">
        {visibleFarms.map((farm) => (
          <li className="farms-discovery-card" key={farm.id}>
            <div className="farms-discovery-heading">
              <h2>
                {farm.id === "bjr-farms" ? (
                  <button type="button" onClick={() => setSelectedFarm(farm)}>
                    {farm.name} <span aria-hidden="true">›</span>
                  </button>
                ) : farm.name}
              </h2>
              <button
                className="farms-follow-button"
                type="button"
                aria-label={`${following[farm.id] ? "Unfollow" : "Follow"} ${farm.name}`}
                aria-pressed={Boolean(following[farm.id])}
                onClick={() => toggleFollow(farm.id)}
              >
                {following[farm.id] ? "Following" : "Follow"}
              </button>
            </div>
            <p className="farms-location">{farm.location}</p>
            <ul className="farms-crop-labels" aria-label={`${farm.name} crops`}>
              {farm.crops.map((crop) => <li key={crop}>{crop}</li>)}
            </ul>
            <p className="farms-bio">{farm.bio}</p>
          </li>
        ))}
      </ul>
      {visibleFarms.length === 0 && (
        <p className="farms-empty" role="status">No farms found. Try another name, place or crop.</p>
      )}
    </section>
  );
}

export default FarmsExplore;
