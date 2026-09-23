import { useEffect, useId, useRef, useState } from "react";
import "./PostCard.css";

function PostCard({ post, showMediaPlaceholder = true, moreButtonType, conversationTarget }) {
  const commentsId = useId();
  const [loved, setLoved] = useState(false);
  const [manuallyOpen, setCommentsOpen] = useState(false);
  const [dismissedTarget, setDismissedTarget] = useState(null);
  const commentsOpen = manuallyOpen || Boolean(conversationTarget && dismissedTarget !== conversationTarget);
  const conversationRef = useRef(null);
  const targetCommentRef = useRef(null);
  const [replyTo, setReplyTo] = useState(null);
  const [comments, setComments] = useState(() => Array.isArray(post.comments) ? post.comments : []);
  const [draft, setDraft] = useState("");
  const [shareFeedback, setShareFeedback] = useState("");
  const sharePending = useRef(false);
  const shareFeedbackTimer = useRef(null);
  const loveCount = (Number.isFinite(post.loves) ? Math.max(0, post.loves) : 0) + Number(loved);

  useEffect(() => () => clearTimeout(shareFeedbackTimer.current), []);

  async function sharePost() {
    if (post.shareable !== true || sharePending.current) return;
    sharePending.current = true;
    clearTimeout(shareFeedbackTimer.current);
    setShareFeedback("");
    const text = `${post.author} on AgriConnect:\n${post.text}`;
    try {
      if (typeof navigator.share === "function") {
        try {
          await navigator.share({ text });
          return;
        } catch (error) {
          if (error?.name === "AbortError") return;
        }
      }
      await navigator.clipboard.writeText(text);
      setShareFeedback("Copied");
    } catch {
      setShareFeedback("Couldn’t copy. Please try again.");
    } finally {
      sharePending.current = false;
      shareFeedbackTimer.current = setTimeout(() => setShareFeedback(""), 3000);
    }
  }

  useEffect(() => {
    if (!conversationTarget) return;
    const target = targetCommentRef.current || conversationRef.current;
    target?.focus({ preventScroll: true });
    target?.scrollIntoView({ block: "center", behavior: "instant" });
  }, [conversationTarget]);

  function addComment(event) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    const entry = { id: crypto.randomUUID(), author: "You", text };
    setComments((current) => replyTo === null
      ? [...current, entry]
      : current.map((comment, index) => index === replyTo
        ? { ...comment, replies: [...(comment.replies || []), entry] }
        : comment));
    setDraft("");
    setReplyTo(null);
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
        <button type="button" aria-label={`Comments, ${comments.length}`} aria-expanded={commentsOpen} aria-controls={commentsId} onClick={() => { setCommentsOpen(!commentsOpen); setDismissedTarget(conversationTarget); }}>
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5a9.5 9.5 0 0 1 19 0Z" />
          </svg>
          <span className="post-action-count">{comments.length}</span>
        </button>
        {post.shareable === true && (
          <button type="button" aria-label="Share post" onClick={sharePost}>
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 15V3m-4 4 4-4 4 4M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8" />
            </svg>
          </button>
        )}
      </div>
      {post.shareable === true && <p className="post-share-feedback" role="status">{shareFeedback}</p>}
      <section ref={conversationRef} tabIndex={-1} id={commentsId} className="post-comments" aria-label={`Comments on ${post.author}'s post`} hidden={!commentsOpen}>
        <ul className="post-comment-list" aria-live="polite" aria-relevant="additions">
          {comments.map((comment, index) => (
            <li key={comment.id || index} ref={conversationTarget?.commentId === comment.id ? targetCommentRef : null} tabIndex={-1}>
              <strong>{comment.author}</strong>
              <p>{comment.text}</p>
              <button className="post-reply-action" type="button" onClick={() => setReplyTo(index)}>Reply</button>
              {comment.replies?.length > 0 && (
                <ul className="post-replies">
                  {comment.replies.map((reply, replyIndex) => (
                    <li key={reply.id || replyIndex}>
                      <strong>{reply.author}</strong>
                      <p>{reply.text}</p>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
        {replyTo !== null && (
          <div className="post-reply-context">
            <span>Replying to {comments[replyTo].author}</span>
            <button type="button" aria-label="Cancel reply" onClick={() => setReplyTo(null)}>×</button>
          </div>
        )}
        <form className="post-comment-form" onSubmit={addComment}>
          <input aria-label={replyTo === null ? "Add a comment" : `Reply to ${comments[replyTo].author}`} placeholder={replyTo === null ? "Add a comment…" : `Reply to ${comments[replyTo].author}…`} value={draft} onChange={(event) => setDraft(event.target.value)} />
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
