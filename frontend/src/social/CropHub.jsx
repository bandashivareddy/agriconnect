import PostCard from "./PostCard";
import "./Explore.css";
import "./CropHub.css";
import { posts } from "./mockSocialData";

function CropHub({ cropKey, cropName, cropIcon, onBack }) {
  const cropPosts = posts.filter(
    (post) => post.cropKey === cropKey
  );

  return (
    <section className="crop-hub">
      <button
        className="explore-back"
        type="button"
        onClick={onBack}
      >
        ← Crops
      </button>

      <div className="crop-hub-header">
        <div className="crop-hub-title">
          <span>{cropIcon}</span>
          <h1>{cropName}</h1>
        </div>

        <p>
          Growers, farms, questions and updates about {cropName.toLowerCase()}.
        </p>
      </div>

      <div className="crop-hub-tabs">
        <button className="active" type="button">Top</button>
        <button type="button">Latest</button>
        <button type="button">Questions</button>
        <button type="button">Farms</button>
        <button type="button">People</button>
      </div>

      <div className="crop-hub-feed">
        {cropPosts.map((post) => (
          <PostCard key={post.id} post={post} moreButtonType="button" />
        ))}
      </div>
    </section>
  );
}

export default CropHub;