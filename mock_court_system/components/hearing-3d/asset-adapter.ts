/**
 * 资产适配器：管理 procedural/VRM/GLB/OBJ/sprite 五级加载。
 *
 * `3D建模方案/角色资料` 是设计源；浏览器只使用 public 下经过优化的派生资产，
 * 不直接复制或读取设计目录。
 */

export type AssetMode = "procedural" | "vrm" | "glb" | "obj" | "sprite"

export interface PbrTextureUrls {
  base_color: string
  metallic: string
  roughness: string
  normal: string
}

export interface CharacterAsset {
  actor_id: string
  mode: AssetMode
  model_url?: string
  texture_urls?: PbrTextureUrls
  sprite_url?: string
  seat_to_root?: [number, number, number]
  forward_axis?: [number, number, number]
  scale?: number
}

const roleModel = (actor_id: string, slug: string, sprite_url?: string): CharacterAsset => ({
  actor_id,
  mode: "obj",
  model_url: `/hearing-3d/models/roles/${slug}/model-optimized.obj`,
  texture_urls: {
    base_color: `/hearing-3d/models/roles/${slug}/base-color.png`,
    metallic: `/hearing-3d/models/roles/${slug}/metallic.png`,
    roughness: `/hearing-3d/models/roles/${slug}/roughness.png`,
    normal: `/hearing-3d/models/roles/${slug}/normal.png`,
  },
  sprite_url,
})

/** 司法警察设计资产在仲裁观庭中映射为会务安保。 */
export const JUDICIAL_POLICE_ASSET: CharacterAsset = {
  actor_id: "judicial_police",
  mode: "obj",
  model_url: "/hearing-3d/models/judicial-police/judicial-police-optimized.obj",
  texture_urls: {
    base_color: "/hearing-3d/models/judicial-police/base-color.png",
    metallic: "/hearing-3d/models/judicial-police/metallic.png",
    roughness: "/hearing-3d/models/judicial-police/roughness.png",
    normal: "/hearing-3d/models/judicial-police/normal.png",
  },
  seat_to_root: [0, 0, 0],
  forward_axis: [0, 0, -1],
  scale: 1,
}

/** 最新角色资料到 Web 优化 OBJ 的一对一运行映射。 */
export const CHARACTER_ASSETS: Record<string, CharacterAsset> = {
  judge: roleModel("judge", "judge"),
  associate_judge: roleModel("associate_judge", "associate-judge"),
  people_juror: roleModel("people_juror", "people-juror"),
  clerk: roleModel("clerk", "clerk"),
  plaintiff_counsel: roleModel("plaintiff_counsel", "china-counsel"),
  prosecutor: roleModel("prosecutor", "prosecutor"),
  china_company_rep: roleModel("china_company_rep", "china-company-rep"),
  defendant_counsel: roleModel("defendant_counsel", "foreign-counsel"),
  defendant_party: roleModel("defendant_party", "foreign-company"),
  interpreter: roleModel("interpreter", "interpreter"),
  technical_expert_witness: roleModel("technical_expert_witness", "technical-expert-witness"),
  fact_witness: roleModel("fact_witness", "foreign-witness"),
  judicial_police: JUDICIAL_POLICE_ASSET,
}

export const ROOM_ASSETS = {
  room_model_url: null as string | null,
  panorama_url: "/hearing-3d/reference/panorama.png",
  desk_items_url: "/hearing-3d/reference/desk-items.png",
  pose_reference_url: "/hearing-3d/reference/pose-reference.png",
}

export async function probeAsset(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: "HEAD" })
    return res.ok
  } catch {
    return false
  }
}
