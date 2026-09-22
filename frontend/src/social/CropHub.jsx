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
          <article className="feed-card" key={post.id}>
            <div className="post-header">
              <div className="avatar">
                {post.author.charAt(0)}
              </div>

              <div className="post-author">
                <strong>{post.author}</strong>
                <span>
                  {post.context} · {post.time}
                </span>
              </div>

              <button
                className="post-more"
                type="button"
                aria-label="More options"
              >
                ···
              </button>
            </div>

            {post.question && (
              <div className="post-type">Question</div>
            )}

            <p className="post-text">{post.text}</p>

            <div className="crop-chip">{post.crop}</div>

            {post.image ? (
              <div className="post-media">
                <img
                  src={post.image}
                  alt={post.imageAlt || ""}
                />
              </div>
            ) : (
              <div className="media-placeholder">
                <span>Farm photo</span>
              </div>
            )}

            <div className="post-actions">
              <button>♡ Useful {post.useful}</button>
              <button>💬 {post.comments}</button>
              <button>↗ Share</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default CropHub;