import { useId, useState } from "react";
import "./PostCard.css";

function PostCard({ post, showMediaPlaceholder = true, moreButtonType }) {
  const commentsId = useId();
  const [loved, setLoved] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [comments, setComments] = useState(() => Array.isArray(post.comments) ? post.comments : []);
  const [draft, setDraft] = useState("");
  const loveCount = (Number.isFinite(post.loves) ? Math.max(0, post.loves) : 0) + Number(loved);

  function addComment(event) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setComments((current) => [...current, { author: "You", text }]);
    setDraft("");
  }

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
        <button type="button" aria-label={`Love, ${loveCount} appreciations`} aria-pressed={loved} onClick={() => setLoved((current) => !current)}>
          <svg className="post-heart-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M20.8 4.8a5.5 5.5 0 0 0-7.8 0L12 5.9l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.4a5.5 5.5 0 0 0 0-7.8Z" />
          </svg>
          <span className="post-action-count">{loveCount}</span>
        </button>
        <button type="button" aria-label={`Comments, ${comments.length}`} aria-expanded={commentsOpen} aria-controls={commentsId} onClick={() => setCommentsOpen((current) => !current)}>
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5a9.5 9.5 0 0 1 19 0Z" />
          </svg>
          <span className="post-action-count">{comments.length}</span>
        </button>
      </div>
      <section id={commentsId} className="post-comments" aria-label={`Comments on ${post.author}'s post`} hidden={!commentsOpen}>
        <ul className="post-comment-list" aria-live="polite" aria-relevant="additions">
          {comments.map((comment, index) => (
            <li key={index}>
              <strong>{comment.author}</strong>
              <p>{comment.text}</p>
            </li>
          ))}
        </ul>
        <form className="post-comment-form" onSubmit={addComment}>
          <input aria-label="Add a comment" placeholder="Add a comment…" value={draft} onChange={(event) => setDraft(event.target.value)} />
          <button type="submit" aria-label="Send comment" disabled={!draft.trim()}>
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="m21 3-7 18-4-7-7-4 18-7Z M10 14 21 3" />
            </svg>
          </button>
        </form>
      </section>
    </article>
  );
}

export default PostCard;
