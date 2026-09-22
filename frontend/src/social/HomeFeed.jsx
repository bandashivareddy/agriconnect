import PostCard from "./PostCard";
import "./HomeFeed.css";
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
          <PostCard key={post.id} post={post} />
        ))}
      </div>
    </div>
  );
}

export default HomeFeed;