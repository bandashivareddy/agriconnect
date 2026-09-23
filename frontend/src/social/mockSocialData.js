import mangoFlowering from "../assets/social/mango-flowering.jpeg";
import bhendiLeaf from "../assets/social/bhendi-leaf.jpeg";
import bullockCartMorning from "../assets/social/bullock-cart-morning.png";

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

export const people = [
  {
    id: "ramesh",
    name: "Ramesh",
    identity: "Mango farmer · Nalgonda",
    bio: "I enjoy watching the orchard change with the seasons and sharing what I learn along the way.",
    interests: ["Mango", "Orchard stories"],
  },
  {
    id: "srinivas",
    name: "Srinivas",
    identity: "Bhendi grower · Nalgonda",
    bio: "Sharing small discoveries from the field and learning from other growers.",
    interests: ["Bhendi", "Growing together"],
  },
  {
    id: "anitha",
    name: "Anitha",
    identity: "Agronomist who loves explaining plants · Hyderabad",
    bio: "Curious about the why behind healthy crops. I share simple observations and enjoy a good crop question.",
    interests: ["Crop knowledge", "Soil life"],
  },
  {
    id: "mahesh",
    name: "Mahesh",
    identity: "Tractor enthusiast · Karimnagar",
    bio: "Happiest talking about machines, sharing field-day photos and hearing how others use their tools.",
    interests: ["Machinery", "Tractors"],
  },
  {
    id: "kavitha",
    name: "Kavitha",
    identity: "Finding nature in everyday farm life · Warangal",
    bio: "Birdsong, rainy mornings and little green things. Sharing the moments that make me stop and look.",
    interests: ["Farm life", "Birds", "Nature"],
  },
];

export const posts = [
  {
    id: 4,
    author: "Suresh",
    context: "Nalgonda, Telangana",
    time: "1h",
    text: "Mornings back home ❤️",
    useful: 18,
    comments: 3,
    image: bullockCartMorning,
    imageAlt: "A bullock cart on a village morning",
  },
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
