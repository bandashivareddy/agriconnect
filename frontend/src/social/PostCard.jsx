import "./PostCard.css";

function PostCard({ post, showMediaPlaceholder = true, moreButtonType }) {
  return (
    <article className="feed-card">
      <div className="post-header">
        <div className="avatar">
          {post.author.charAt(0)}
        </div>

        <div className="post-author">
          <strong>{post.author}</strong>
          <span>{post.context} · {post.time}</span>
        </div>

        <button className="post-more" type={moreButtonType} aria-label="More options">
          ···
        </button>
      </div>

      {post.question && (
        <div className="post-type">Question</div>
      )}

      <p className="post-text">{post.text}</p>

      {typeof post.crop === "string" && post.crop.trim() && (
        <div className="crop-chip">{post.crop}</div>
      )}
    
      {post.image ? (
        <div className="post-media">
          <img
            src={post.image}
            alt={post.imageAlt || ""}
          />
        </div>
      ) : showMediaPlaceholder ? (
        <div className="media-placeholder">
          <span>Farm photo</span>
        </div>
      ) : null}
      <div className="post-actions">
        <button>♡ Useful {post.useful}</button>
        <button>💬 {post.comments}</button>
        <button>↗ Share</button>
      </div>
    </article>
  );
}

export default PostCard;
