import { useEffect, useRef, useState } from "react";
import { farms, posts } from "./mockSocialData";
import "./CreatePost.css";

const crops = [...new Set([
  ...posts
    .map((post) => post.cropKey)
    .filter((cropKey) => typeof cropKey === "string" && cropKey.trim())
    .map((cropKey) => cropKey.charAt(0).toUpperCase() + cropKey.slice(1)),
  ...farms.flatMap((farm) => farm.crops),
])];

function CreatePost({ onClose }) {
  const dialog = useRef(null);
  const [text, setText] = useState("");
  const [crop, setCrop] = useState("");
  const [farmId, setFarmId] = useState("");
  const [context, setContext] = useState(null);
  const [question, setQuestion] = useState(false);
  const [mediaNotice, setMediaNotice] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);

  function submit(event) {
    event.preventDefault();
    if (text.trim()) setSubmitted(true);
  }

  return (
    <dialog
      ref={dialog}
      className="create-post"
      aria-labelledby="create-post-heading"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
    >
      <header className="create-post-header">
        <button className="create-post-close" type="button" aria-label="Close" onClick={onClose} autoFocus>
          <span aria-hidden="true">×</span>
        </button>
        <h1 id="create-post-heading">Share something</h1>
        {!submitted && (
          <button className="create-post-submit" type="submit" form="create-post-form" disabled={!text.trim()}>Post</button>
        )}
      </header>
      {submitted ? (
        <div className="create-post-confirmation">
          <p role="status">Preview complete. Your post hasn’t been published.</p>
          <button className="create-post-submit" type="button" onClick={onClose}>Done</button>
        </div>
      ) : (
        <form id="create-post-form" onSubmit={submit}>
          <button className="create-post-media" type="button" onClick={() => setMediaNotice(true)}>
            <span aria-hidden="true">📷</span>
            <strong>Photo / Video</strong>
            <small>Share a moment from around farming</small>
          </button>
          {mediaNotice && <p className="create-post-note" role="status">Photo and video sharing is coming soon.</p>}
          <textarea
            className="create-post-text"
            aria-label="What's happening?"
            placeholder="What's happening?"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="create-post-context" aria-label="Optional context">
            <button type="button" aria-expanded={context === "crop"} onClick={() => setContext(context === "crop" ? null : "crop")}>
              {crop ? `Crop: ${crop}` : "Add crop"}
            </button>
            {crop && <button type="button" aria-label="Remove crop" onClick={() => setCrop("")}>×</button>}
            <button type="button" aria-expanded={context === "farm"} onClick={() => setContext(context === "farm" ? null : "farm")}>
              {farmId ? `Farm: ${farms.find((farm) => farm.id === farmId).name}` : "Add farm"}
            </button>
            {farmId && <button type="button" aria-label="Remove farm" onClick={() => setFarmId("")}>×</button>}
            <button type="button" aria-pressed={question} onClick={() => setQuestion(!question)}>
              {question ? "✓ Ask as a question" : "Ask as a question"}
            </button>
          </div>
          {context === "crop" && (
            <label className="create-post-picker">
              Add a crop, if you like
              <select value={crop} onChange={(event) => { setCrop(event.target.value); setContext(null); }}>
                <option value="">No crop</option>
                {crops.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>
          )}
          {context === "farm" && (
            <label className="create-post-picker">
              Add a farm, if you like
              <select value={farmId} onChange={(event) => { setFarmId(event.target.value); setContext(null); }}>
                <option value="">No farm</option>
                {farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}
              </select>
            </label>
          )}
          {question && <p className="create-post-note" role="status">This will be a community question.</p>}
          <footer className="create-post-footer">
            <span>Preview only for now</span>
          </footer>
        </form>
      )}
    </dialog>
  );
}

export default CreatePost;
