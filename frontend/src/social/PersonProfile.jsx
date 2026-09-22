import { posts } from "./mockSocialData";
import PostCard from "./PostCard";
import "./Explore.css";
import "./PersonProfile.css";

function PersonProfile({ person, following, onToggleFollow, onBack }) {
  const publicPosts = posts.filter((post) => post.author === person.name);

  return (
    <section className="person-profile">
      <button className="explore-back" type="button" onClick={onBack}>← People</button>
      <header className="person-profile-header">
        <div className="person-profile-heading">
          <div className="person-profile-avatar" aria-hidden="true">{person.name.charAt(0)}</div>
          <h1>{person.name}</h1>
          <button
            className="person-profile-follow"
            type="button"
            aria-label={`${following ? "Unfollow" : "Follow"} ${person.name}`}
            aria-pressed={following}
            onClick={onToggleFollow}
          >
            {following ? "Following" : "Follow"}
          </button>
        </div>
        <p className="person-profile-identity">{person.identity}</p>
        <p className="person-profile-bio">{person.bio}</p>
      </header>
      <section className="person-profile-posts" aria-label="Public posts">
        <h2>Posts</h2>
        {publicPosts.map((post) => <PostCard key={post.id} post={post} />)}
      </section>
    </section>
  );
}

export default PersonProfile;
