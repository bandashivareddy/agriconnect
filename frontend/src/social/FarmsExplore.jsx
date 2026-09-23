import { useContext, useState } from "react";
import { SocialPeopleContext } from "./SocialPeopleContext";
import { farms } from "./mockSocialData";
import FarmProfile from "./FarmProfile";
import "./Explore.css";
import "./FarmsExplore.css";

function FarmsExplore({ onBack }) {
  const [query, setQuery] = useState("");
  const [selectedFarm, setSelectedFarm] = useState(null);
  const { followedFarmIds, toggleFarmFollow } = useContext(SocialPeopleContext);

  if (selectedFarm) {
    return (
      <FarmProfile
        farm={selectedFarm}
        following={followedFarmIds.includes(selectedFarm.id)}
        onToggleFollow={() => toggleFarmFollow(selectedFarm.id)}
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
                <button type="button" onClick={() => setSelectedFarm(farm)}>
                  {farm.name} <span aria-hidden="true">›</span>
                </button>
              </h2>
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
