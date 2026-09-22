import PostCard from "./PostCard";
import "./Explore.css";
import "./QuestionsExplore.css";
import { posts } from "./mockSocialData";

function QuestionsExplore({ onBack }) {
  const questions = posts.filter((post) => post.question);

  return (
    <section className="questions-explore">
      <button
        className="explore-back"
        type="button"
        onClick={onBack}
      >
        ← Explore
      </button>

      <div className="questions-header">
        <h1>Problems & Questions</h1>
        <p>
          Get help from people who have seen it in the field.
        </p>
      </div>

      <label className="explore-search questions-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          placeholder="Search problems and questions..."
          aria-label="Search problems and questions"
        />
      </label>

      <div className="ask-community-card">
        <div>
          <strong>Have a problem?</strong>
          <p>
            Share a photo or describe what you're seeing.
          </p>
        </div>

        <button type="button">
          Ask Community
        </button>
      </div>

      <section className="questions-section">
        <h2>Browse by crop</h2>

        <div className="question-crop-chips">
          <button type="button">🥭 Mango</button>
          <button type="button">🌱 Bhendi</button>
          <button type="button">🌾 Paddy</button>
          <button type="button">☁️ Cotton</button>
          <button type="button">🌶️ Chilli</button>
        </div>
      </section>

      <section className="questions-section">
        <h2>Recent questions</h2>

        <div className="questions-feed">
          {questions.map((post) => (
            <PostCard key={post.id} post={post} showMediaPlaceholder={false} moreButtonType="button" />
          ))}
        </div>
      </section>
    </section>
  );
}

export default QuestionsExplore;