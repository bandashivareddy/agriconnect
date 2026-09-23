import mangoFlowering from "../assets/social/mango-flowering.jpeg";
import bhendiLeaf from "../assets/social/bhendi-leaf.jpeg";
import bullockCartMorning from "../assets/social/bullock-cart-morning.png";
import paddyPlanting from "../assets/social/paddy-planting.png";
import chilliHarvest from "../assets/social/chilli-harvest.png";

export const farms = [
  {
    id: "bjr-farms",
    name: "BJR Farms",
    location: "Nalgonda, Telangana",
    crops: ["Mango", "Coconut", "Oil Palm"],
    bio: "Sharing seasonal moments, orchard stories and everyday discoveries from our farm.",
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
    id: "suresh",
    name: "Suresh",
    identity: "Nalgonda, Telangana",
    bio: "Sharing everyday moments and memories from back home.",
    interests: ["Village life", "Home"],
  },
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
    shareable: true,
    author: "Suresh",
    personId: "suresh",
    context: "Nalgonda, Telangana",
    time: "1h",
    text: "Mornings back home ❤️",
    loves: 18,
    comments: [
      { id: "suresh-raju", author: "Raju", text: "Looks just like our side during the rains ❤️" },
      {
        id: "suresh-road",
        author: "You",
        text: "I remember taking this road to visit my grandparents.",
        replies: [
          { id: "suresh-road-reply", author: "Suresh", text: "The old neem tree is still there 😊" },
        ],
      },
    ],
    image: bullockCartMorning,
    imageAlt: "A bullock cart on a village morning",
  },
  {
    id: 1,
    shareable: true,
    author: "Ramesh",
    personId: "ramesh",
    farmId: "bjr-farms",
    context: "Mango farmer · Nalgonda",
    time: "2h",
    text: "Good flowering this week. The trees that were pruned after harvest are looking noticeably better.",
    crop: "🥭 Mango",
    cropKey: "mango",
    loves: 34,
    image: mangoFlowering,
    imageAlt: "Mango flowering",
  },
  {
    id: 5,
    shareable: true,
    author: "Raju",
    context: "Paddy farmer · Suryapet, Telangana",
    time: "3h",
    text: "Planting started today 🌱",
    crop: "🌾 Paddy",
    cropKey: "paddy",
    loves: 21,
    image: paddyPlanting,
    imageAlt: "Paddy transplantation work in a field",
  },
  {
    id: 2,
    shareable: true,
    author: "Srinivas",
    personId: "srinivas",
    context: "Bhendi grower · Nalgonda",
    time: "4h",
    text: "Some of my bhendi leaves are getting damaged like this. Has anyone seen this before? What could be causing it?",
    crop: "🌱 Bhendi",
    cropKey: "bhendi",
    loves: 12,
    question: true,
    image: bhendiLeaf,
    imageAlt: "Damaged bhendi leaves",
  },
  {
    id: 3,
    shareable: true,
    author: "Lakshmi",
    context: "Farm update · Warangal",
    time: "6h",
    text: "First harvest from this plot today. Small beginning, but a satisfying one.",
    crop: "🌶️ Chilli",
    cropKey: "chilli",
    loves: 57,
    comments: [
      { id: "lakshmi-raju", author: "Raju", text: "A lovely first harvest. Happy for you!" },
    ],
    image: chilliHarvest,
    imageAlt: "Chilli harvest",
  },
];

// Pre-existing inbox examples for the mock viewer (Lakshmi), not live activity.
export const notifications = [
  {
    id: "harvest-comment",
    type: "comment",
    author: "Raju",
    text: "A lovely first harvest. Happy for you!",
    postId: 3,
    commentId: "lakshmi-raju",
    read: false,
  },
  {
    id: "village-reply",
    type: "reply",
    author: "Suresh",
    text: "The old neem tree is still there 😊",
    postId: 4,
    commentId: "suresh-road",
    read: false,
  },
];
