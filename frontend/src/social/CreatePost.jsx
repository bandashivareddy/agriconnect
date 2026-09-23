import { useEffect, useRef, useState } from "react";
import { farms, posts } from "./mockSocialData";
import { normalizePublicContext } from "./publicPostContext";
import "./CreatePost.css";

const crops = [...new Set([
  ...posts
    .map((post) => post.cropKey)
    .filter((cropKey) => typeof cropKey === "string" && cropKey.trim())
    .map((cropKey) => cropKey.charAt(0).toUpperCase() + cropKey.slice(1)),
  ...farms.flatMap((farm) => farm.crops),
])];

// Initial context is a snapshot for this composer mount; edits remain local.
function CreatePost({ user, onClose, onPost, initialContext }) {
  const dialog = useRef(null);
  const [text, setText] = useState("");
  const [crop, setCrop] = useState(() => normalizePublicContext(initialContext).crop);
  const [farm, setFarm] = useState(() => normalizePublicContext(initialContext).farm);
  const [context, setContext] = useState(null);
  const [question, setQuestion] = useState(false);
  const [mediaNotice, setMediaNotice] = useState(false);
  const submitted = useRef(false);
  const authorPerson = {
    id: `user:${user?.user_id ?? "current"}`,
    name: user?.full_name?.trim() || "You",
  };

  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);

  function submit(event) {
    event.preventDefault();
    if (!text.trim() || submitted.current) return;
    const publicContext = normalizePublicContext({ farm, crop });
    const post = {
      id: crypto.randomUUID(),
      personId: authorPerson.id,
      author: authorPerson.name,
      time: "Just now",
      text: text.trim(),
      ...(publicContext.farm || publicContext.crop ? { publicContext } : {}),
      // Keep existing mock Following/crop consumers compatible. Canonical IDs
      // must never be placed in these mock identity fields.
      ...(publicContext.farm?.socialFarmId ? { farmId: publicContext.farm.socialFarmId } : {}),
      ...(publicContext.crop?.socialCropKey ? { cropKey: publicContext.crop.socialCropKey, crop: publicContext.crop.name } : {}),
      ...(question ? { question: true } : {}),
    };
    submitted.current = true;
    onPost(post);
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
          <button className="create-post-submit" type="submit" form="create-post-form" disabled={!text.trim()}>Post</button>
      </header>
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
          <p className="create-post-context-label">Add context <span>(optional)</span></p>
          <div className="create-post-context" aria-label="Optional context">
            <button type="button" aria-expanded={context === "crop"} onClick={() => setContext(context === "crop" ? null : "crop")}>
              {crop ? `Crop: ${crops.find((name) => name.toLowerCase() === crop.socialCropKey) || crop.name}` : "Add crop"}
            </button>
            {crop && <button type="button" aria-label="Remove crop" onClick={() => setCrop(undefined)}>×</button>}
            <button type="button" aria-expanded={context === "farm"} onClick={() => setContext(context === "farm" ? null : "farm")}>
              {farm ? `Farm: ${farm.name}` : "Add farm"}
            </button>
            {farm && <button type="button" aria-label="Remove farm" onClick={() => setFarm(undefined)}>×</button>}
            <button type="button" aria-pressed={question} onClick={() => setQuestion(!question)}>
              {question ? "✓ Ask as a question" : "Ask as a question"}
            </button>
          </div>
          {context === "crop" && (
            <label className="create-post-picker">
              Add a crop, if you like
              <select value={crop?.canonicalCropId ? `canonical:${crop.canonicalCropId}` : crop?.socialCropKey || ""} onChange={(event) => { if (!event.target.value.startsWith("canonical:")) setCrop(normalizePublicContext({ crop: { socialCropKey: event.target.value } }).crop); setContext(null); }}>
                <option value="">No crop</option>
                {crop?.canonicalCropId && <option value={`canonical:${crop.canonicalCropId}`}>{crop.name}</option>}
                {crops.map((name) => <option key={name} value={name.toLowerCase()}>{name}</option>)}
              </select>
            </label>
          )}
          {context === "farm" && (
            <label className="create-post-picker">
              Add a farm, if you like
              <select value={farm?.canonicalFarmId ? `canonical:${farm.canonicalFarmId}` : farm?.socialFarmId || ""} onChange={(event) => { if (!event.target.value.startsWith("canonical:")) setFarm(normalizePublicContext({ farm: { socialFarmId: event.target.value } }).farm); setContext(null); }}>
                <option value="">No farm</option>
                {farm?.canonicalFarmId && <option value={`canonical:${farm.canonicalFarmId}`}>{farm.name}</option>}
                {farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}
              </select>
            </label>
          )}
          {question && <p className="create-post-note" role="status">This will be a community question.</p>}
          <footer className="create-post-footer">
            <span>Visible for this session only</span>
          </footer>
        </form>
    </dialog>
  );
}

export default CreatePost;
