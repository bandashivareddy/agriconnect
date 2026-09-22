import { posts } from "./mockSocialData";

function HomeFeed() {
  return (
    <div className="social-home">
      <div className="feed-tabs">
        <button className="feed-tab active">For You</button>
        <button className="feed-tab">Following</button>
        <button className="feed-tab">Nearby</button>
      </div>

      <div className="feed">
        {posts.map((post) => (
          <article className="feed-card" key={post.id}>
            <div className="post-header">
              <div className="avatar">
                {post.author.charAt(0)}
              </div>

              <div className="post-author">
                <strong>{post.author}</strong>
                <span>{post.context} · {post.time}</span>
              </div>

              <button className="post-more" aria-label="More options">
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
    </div>
  );
}

export default HomeFeed;