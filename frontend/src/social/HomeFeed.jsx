import PostCard from "./PostCard";
import "./HomeFeed.css";
import { posts } from "./mockSocialData";

function HomeFeed({ conversationTarget }) {
  return (
    <div className="social-home">
      <div className="feed-tabs">
        <button className="feed-tab active">For You</button>
        <button className="feed-tab">Following</button>
        <button className="feed-tab">Nearby</button>
      </div>

      <div className="feed">
        {posts.map((post) => (
          <PostCard key={post.id} post={post} conversationTarget={conversationTarget?.postId === post.id ? conversationTarget : null} />
        ))}
      </div>
    </div>
  );
}

export default HomeFeed;
