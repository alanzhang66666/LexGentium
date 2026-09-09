/** Official assets replace capsules by setting skins.*.model to a public path. */
export function isReplaceableModelPath(path: string | undefined | null): boolean {
  if (!path) return false
  return /\.(glb|gltf|vrm)$/i.test(path)
}

export const JUDGE_SWAP_MODEL = "/court3d/models/judge_presiding_m.vrm"
