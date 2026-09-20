/** Skin-like PBR that still uses the supplier albedo / roughness / metalness maps. */
export const FACE_MATERIAL_PRESET = {
  metalness: 1,
  roughness: 1,
  sheen: 0.4,
  sheenRoughness: 0.56,
  clearcoat: 0.04,
  clearcoatRoughness: 0.64,
  envMapIntensity: 0.36,
  normalScale: 0.3,
  maxAnisotropy: 16,
} as const
