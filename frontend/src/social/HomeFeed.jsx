const posts = [
  {
    id: 1,
    author: "Ramesh",
    context: "Mango farmer · Nalgonda",
    time: "2h",
    text: "Good flowering this week. The trees that were pruned after harvest are looking noticeably better.",
    crop: "🥭 Mango",
    useful: 34,
    comments: 8,
  },
  {
    id: 2,
    author: "Srinivas",
    context: "Cotton grower",
    time: "4h",
    text: "Seeing these spots on younger cotton leaves. Has anyone faced this recently?",
    crop: "🌱 Cotton",
    useful: 12,
    comments: 19,
    question: true,
  },
  {
    id: 3,
    author: "Lakshmi",
    context: "Farm update · Warangal",
    time: "6h",
    text: "First harvest from this plot today. Small beginning, but a satisfying one.",
    crop: "🌶️ Chilli",
    useful: 57,
    comments: 11,
  },
];

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

            <div className="media-placeholder">
              <span>Farm photo</span>
            </div>

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