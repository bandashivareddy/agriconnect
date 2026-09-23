import { useContext, useState } from "react";
import { SocialPeopleContext } from "./SocialPeopleContext";
import { people } from "./mockSocialData";
import PersonProfile from "./PersonProfile";
import "./Explore.css";
import "./PeopleExplore.css";

function PeopleExplore({ onBack }) {
  const [query, setQuery] = useState("");
  const [selectedPerson, setSelectedPerson] = useState(null);
  const { followedPersonIds, toggleFollow } = useContext(SocialPeopleContext);

  if (selectedPerson) {
    return (
      <PersonProfile
        person={selectedPerson}
        following={followedPersonIds.includes(selectedPerson.id)}
        onToggleFollow={() => toggleFollow(selectedPerson.id)}
        onBack={() => setSelectedPerson(null)}
      />
    );
  }

  const search = query.trim().toLowerCase();
  const visiblePeople = people.filter((person) =>
    [person.name, person.identity, person.bio, ...person.interests]
      .join(" ").toLowerCase().includes(search)
  );

  return (
    <section className="people-explore">
      <button className="explore-back" type="button" onClick={onBack}>← Explore</button>
      <div className="explore-header">
        <h1>People</h1>
        <p>Find people whose stories, ideas and everyday discoveries you’ll enjoy.</p>
      </div>
      <label className="explore-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          aria-label="Search people"
          placeholder="Search people, places or interests..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <ul className="people-discovery-list">
        {visiblePeople.map((person) => (
          <li className="people-discovery-card" key={person.id}>
            <div className="people-discovery-heading">
              <div className="people-avatar" aria-hidden="true">{person.name.charAt(0)}</div>
              <h2>
                  <button type="button" onClick={() => setSelectedPerson(person)}>
                    {person.name} <span aria-hidden="true">›</span>
                  </button>
              </h2>
              <button
                className="people-follow"
                type="button"
                aria-label={`${followedPersonIds.includes(person.id) ? "Unfollow" : "Follow"} ${person.name}`}
                aria-pressed={followedPersonIds.includes(person.id)}
                onClick={() => toggleFollow(person.id)}
              >
                {followedPersonIds.includes(person.id) ? "Following" : "Follow"}
              </button>
            </div>
            <p className="people-identity">{person.identity}</p>
            <p className="people-bio">{person.bio}</p>
            <ul className="people-interests" aria-label={`${person.name}'s interests`}>
              {person.interests.map((interest) => <li key={interest}>{interest}</li>)}
            </ul>
          </li>
        ))}
      </ul>
      {visiblePeople.length === 0 && (
        <p className="people-empty" role="status">No people found. Try another name, place or interest.</p>
      )}
    </section>
  );
}

export default PeopleExplore;
