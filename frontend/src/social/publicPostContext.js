import { farms, posts } from "./mockSocialData";

const validId = (id) => Number.isSafeInteger(id) && id > 0;
const displayName = (name) => typeof name === "string" ? name.trim() : "";

// Copy only public identity and display fields. Never spread operational objects.
// canonicalCropId is crops.crop_id, never the cultivation's farm_crop_id.
// Canonical references deliberately have no mock profile/navigation identity.
export function normalizePublicContext(value) {
  const context = {};
  const farm = value?.farm;
  const crop = value?.crop;
  if (validId(farm?.canonicalFarmId) && displayName(farm?.name)) {
    context.farm = { canonicalFarmId: farm.canonicalFarmId, name: displayName(farm.name) };
  } else if (farm?.canonicalFarmId === undefined) {
    const profile = farms.find((entry) => entry.id === farm?.socialFarmId);
    if (profile) context.farm = { socialFarmId: profile.id, name: profile.name };
  }
  if (validId(crop?.canonicalCropId) && displayName(crop?.name)) {
    context.crop = { canonicalCropId: crop.canonicalCropId, name: displayName(crop.name) };
  } else if (crop?.canonicalCropId === undefined && typeof crop?.socialCropKey === "string") {
    const key = crop.socialCropKey;
    const post = posts.find((entry) => entry.cropKey === key);
    const name = farms.flatMap((entry) => entry.crops).find((entry) => entry.toLowerCase() === key);
    if (post || name) context.crop = { socialCropKey: key, name: post?.crop || name };
  }
  return context;
}
