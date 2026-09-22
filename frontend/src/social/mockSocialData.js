import mangoFlowering from "../assets/social/mango-flowering.jpeg";
import bhendiLeaf from "../assets/social/bhendi-leaf.jpeg";

export const farms = [
  {
    id: "bjr-farms",
    name: "BJR Farms",
    location: "Nalgonda, Telangana",
    crops: ["Mango", "Coconut", "Oil Palm"],
    bio: "Sharing seasonal moments, orchard stories and everyday discoveries from our farm.",
    postIds: [1],
  },
  {
    id: "manjeera-farms",
    name: "Manjeera Farms",
    location: "Sangareddy, Telangana",
    crops: ["Paddy", "Groundnut"],
    bio: "Following the seasons and sharing little moments from the fields.",
  },
  {
    id: "palapitta-farm",
    name: "Palapitta Farm",
    location: "Warangal, Telangana",
    crops: ["Chilli", "Cotton"],
    bio: "Field photos, fresh growth and conversations with fellow growers.",
  },
  {
    id: "godavari-groves",
    name: "Godavari Groves",
    location: "Rajahmundry, Andhra Pradesh",
    crops: ["Coconut", "Banana"],
    bio: "A glimpse of life among the palms and banana plants.",
  },
];

export const posts = [
  {
    id: 1,
    author: "Ramesh",
    context: "Mango farmer · Nalgonda",
    time: "2h",
    text: "Good flowering this week. The trees that were pruned after harvest are looking noticeably better.",
    crop: "🥭 Mango",
    cropKey: "mango",
    useful: 34,
    comments: 8,
    image: mangoFlowering,
    imageAlt: "Mango flowering",
  },
  {
    id: 2,
    author: "Srinivas",
    context: "Bhendi grower · Nalgonda",
    time: "4h",
    text: "Some of my bhendi leaves are getting damaged like this. Has anyone seen this before? What could be causing it?",
    crop: "🌱 Bhendi",
    cropKey: "bhendi",
    useful: 12,
    comments: 19,
    question: true,
    image: bhendiLeaf,
    imageAlt: "Damaged bhendi leaves",
  },
  {
    id: 3,
    author: "Lakshmi",
    context: "Farm update · Warangal",
    time: "6h",
    text: "First harvest from this plot today. Small beginning, but a satisfying one.",
    crop: "🌶️ Chilli",
    cropKey: "chilli",
    useful: 57,
    comments: 11,
  },
];
