import "./Explore.css";
import { useState } from "react";
import CropExplore from "./CropExplore";
import QuestionsExplore from "./QuestionsExplore";

function Explore() {
  const [view, setView] = useState("main");

  if (view === "crops") {
    return (
      <CropExplore
        onBack={() => setView("main")}
      />
    );
  }

  if (view === "questions") {
    return (
      <QuestionsExplore
        onBack={() => setView("main")}
      />
    );
  }

  return (
    <section className="explore-page">
      <div className="explore-header">
        <h1>Explore</h1>
        <p>Find what you need in farming.</p>
      </div>

      <label className="explore-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          placeholder="Search crops, problems, farms, people..."
          aria-label="Search AgriConnect"
        />
      </label>

      <section className="explore-section">
        <h2>Browse</h2>

        <div className="explore-primary-grid">
          <button
            type="button"
            onClick={() => setView("crops")}
          >
            <span>🌾</span>
            <strong>Crops</strong>
            <small>
              Updates, questions and knowledge by crop
            </small>
          </button>

          <button
            type="button"
            onClick={() => setView("questions")}
          >
            <span>❓</span>
            <strong>Problems & Questions</strong>
            <small>
              Find answers from the farming community
            </small>
          </button>
        </div>
      </section>

      <section className="explore-section">
        <h2>Discover</h2>

        <div className="explore-discovery-list">
          <button type="button">
            <span>🌱</span>

            <div>
              <strong>Farms</strong>
              <small>
                Discover farms and what they are growing
              </small>
            </div>

            <span className="explore-arrow">›</span>
          </button>

          <button type="button">
            <span>👥</span>

            <div>
              <strong>People</strong>
              <small>
                Find farmers and people in agriculture
              </small>
            </div>

            <span className="explore-arrow">›</span>
          </button>
        </div>
      </section>

      <section className="explore-section">
        <h2>Get things done</h2>

        <button className="explore-services" type="button">
          <span>🛠</span>

          <div>
            <strong>Services</strong>
            <small>
              Find agricultural services and providers
            </small>
          </div>

          <span className="explore-arrow">›</span>
        </button>
      </section>
    </section>
  );
}

export default Explore;