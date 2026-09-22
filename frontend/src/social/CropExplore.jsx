import "./Explore.css";
import "./CropExplore.css";
import { useState } from "react";
import CropHub from "./CropHub";

function CropExplore({ onBack }) {
  const [selectedCrop, setSelectedCrop] = useState(null);

  const crops = [
    { name: "Mango", icon: "🥭", key: "mango" },
    { name: "Paddy", icon: "🌾", key: "paddy" },
    { name: "Cotton", icon: "☁️", key: "cotton" },
    { name: "Chilli", icon: "🌶️", key: "chilli" },
    { name: "Bhendi", icon: "🌱", key: "bhendi" },
    { name: "Groundnut", icon: "🥜", key: "groundnut" },
  ];

  if (selectedCrop) {
    return (
      <CropHub
        cropKey={selectedCrop.key}
        cropName={selectedCrop.name}
        cropIcon={selectedCrop.icon}
        onBack={() => setSelectedCrop(null)}
      />
    );
  }

  return (
    <section className="crop-explore">
      <button
        className="explore-back"
        type="button"
        onClick={onBack}
      >
        ← Explore
      </button>

      <div className="explore-header">
        <h1>Crops</h1>
        <p>Discover what farmers are growing and talking about.</p>
      </div>

      <div className="crop-list">
        {crops.map((crop) => (
          <button
            className="crop-discovery-card"
            type="button"
            key={crop.key}
            onClick={
              crop.key === "mango"
                ? () => setSelectedCrop(crop)
                : undefined
            }
          >
            <span className="crop-discovery-icon">
              {crop.icon}
            </span>

            <span className="crop-discovery-name">
              {crop.name}
            </span>

            <span className="crop-discovery-arrow">
              ›
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

export default CropExplore;