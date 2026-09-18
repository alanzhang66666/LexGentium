/**
 * 资产适配器：管理 procedural/VRM/GLB/OBJ/sprite 五级加载。
 *
 * 模式：
 * - "procedural" : 程序化 3D 坐姿人偶（默认，真 3D 几何体，无需模型文件）
 * - "vrm"        : @pixiv/three-vrm 加载 VRM 模型（正式角色模型，需要 .vrm 文件）
 * - "glb"        : GLTFLoader 加载 GLB 模型（房间/道具/替代角色）
 * - "obj"        : OBJLoader 加载 OBJ + PBR 贴图（供应商交付的静态角色模型）
 * - "sprite"     : Billboard 照片立牌（参考图 PNG/JPG 作为 2D 面板）
 *
 * 正式 VRM/GLB 文件放入 public/hearing-3d/models/ 后，
 * 只需在 CHARACTER_ASSETS 中改 mode 并填 model_url，场景代码不变。
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
  /** VRM/GLB 文件路径（相对于 public/），mode=vrm/glb 时必填 */
  model_url?: string
  /** OBJ 模型使用的 PBR 贴图路径，mode=obj 时必填 */
  texture_urls?: PbrTextureUrls
  /** 参考图路径（mode=sprite 时用作 billboard 贴图） */
  sprite_url?: string
  /** VRM/GLB 模型校准参数 */
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

/** 供应商新增的人物 OBJ 资产；保留 sprite_url 作为回退和身份参考。 */
export const CHARACTER_ASSETS: Record<string, CharacterAsset> = {
  judge:             roleModel("judge", "judge", "/hearing-3d/reference/char-9-web.jpg"),
  clerk:             roleModel("clerk", "clerk", "/hearing-3d/reference/char-6-web.jpg"),
  plaintiff_counsel: roleModel("plaintiff_counsel", "china-counsel", "/hearing-3d/reference/char-8-web.jpg"),
  plaintiff_party:   roleModel("plaintiff_party", "foreign-defendant", "/hearing-3d/reference/char-1-web.jpg"),
  defendant_counsel: roleModel("defendant_counsel", "foreign-counsel", "/hearing-3d/reference/char-4-web.jpg"),
  defendant_party:   roleModel("defendant_party", "foreign-company", "/hearing-3d/reference/char-3-web.jpg"),
  interpreter:       roleModel("interpreter", "interpreter", "/hearing-3d/reference/char-5-web.jpg"),
  prosecutor:        roleModel("prosecutor", "prosecutor"),
  fact_witness:      roleModel("fact_witness", "foreign-witness"),
}

/** 供应商交付的司法警察静态 OBJ 资产。由 JudicialPoliceModel 在听证场景中加载。 */
export const JUDICIAL_POLICE_ASSET: CharacterAsset = {
  actor_id: "judicial_police",
  mode: "obj",
  // 浏览器运行时使用保留 UV 的轻量化 OBJ；原始交付文件仍保留在同目录。
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

/** 房间环境资产 */
export const ROOM_ASSETS = {
  /** 正式房间 GLB 到位后替换 */
  room_model_url: null as string | null,
  /** 全景渲染图作为环境参考/背景面板 */
  panorama_url: "/hearing-3d/reference/panorama.png",
  /** 桌面物品参考图 */
  desk_items_url: "/hearing-3d/reference/desk-items.png",
  /** 姿势参考图 */
  pose_reference_url: "/hearing-3d/reference/pose-reference.png",
}

/** 检查 VRM/GLB 文件是否存在（运行时探针） */
export async function probeAsset(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: "HEAD" })
    return res.ok
  } catch {
    return false
  }
}
