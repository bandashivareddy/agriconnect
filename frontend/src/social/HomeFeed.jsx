import { useContext } from "react";
import { SocialPeopleContext } from "./SocialPeopleContext";
import PostCard from "./PostCard";
import "./HomeFeed.css";
import { posts } from "./mockSocialData";

function HomeFeed({ conversationTarget, feedTab = "for-you", onChangeTab, sessionPosts = [] }) {
  const socialPeople = useContext(SocialPeopleContext);
  const homePosts = [...sessionPosts, ...posts];
  const visiblePosts = feedTab === "following"
    ? homePosts.filter((post) => socialPeople?.followedPersonIds.includes(post.personId)
      || socialPeople?.followedFarmIds.includes(post.farmId))
    : homePosts;
  return (
    <div className="social-home">
      <div className="feed-tabs">
        <button type="button" className={`feed-tab ${feedTab === "for-you" ? "active" : ""}`} aria-pressed={feedTab === "for-you"} onClick={() => onChangeTab?.("for-you")}>For You</button>
        <button type="button" className={`feed-tab ${feedTab === "following" ? "active" : ""}`} aria-pressed={feedTab === "following"} onClick={() => onChangeTab?.("following")}>Following</button>
        <button className="feed-tab">Nearby</button>
      </div>

      <div className="feed">
        {visiblePosts.length === 0 && <p className="following-empty" role="status">Posts from people and farms you follow will appear here.</p>}
        {visiblePosts.map((post) => {
          const isSessionPost = sessionPosts.includes(post);
          return <PostCard key={post.id} post={post} authorPerson={isSessionPost ? { id: post.personId, name: post.author } : undefined} showMediaPlaceholder={!isSessionPost} conversationTarget={conversationTarget?.postId === post.id ? conversationTarget : null} />;
        })}
      </div>
    </div>
  );
}

export default HomeFeed;
