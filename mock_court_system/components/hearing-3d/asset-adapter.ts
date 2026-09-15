/**
 * 资产适配器：管理 VRM/GLB/Reference 三级加载。
 *
 * 三种模式：
 * - "vrm"    : @pixiv/three-vrm 加载 VRM 模型（正式角色模型，需要 .vrm 文件）
 * - "glb"    : GLTFLoader 加载 GLB 模型（房间/道具/替代角色）
 * - "sprite" : Billboard sprite（使用参考图 PNG 作为高质量 2D 面板）
 *
 * 正式 VRM/GLB 文件放入 public/hearing-3d/models/ 后，
 * 只需在 ASSET_MANIFEST 中更新 model_url 即可切换，不改 3D 场景代码。
 */

export type AssetMode = "vrm" | "glb" | "sprite"

export interface CharacterAsset {
  actor_id: string
  mode: AssetMode
  /** VRM/GLB 文件路径（相对于 public/），mode=vrm/glb 时必填 */
  model_url?: string
  /** 参考图路径（mode=sprite 时用作 billboard 贴图） */
  sprite_url?: string
  /** VRM/GLB 模型校准参数 */
  seat_to_root?: [number, number, number]
  forward_axis?: [number, number, number]
  scale?: number
}

/** 当前资产清单：正式 VRM/GLB 未交付，使用参考图 sprite 模式。
 *  正式模型到位后，将 mode 改为 "vrm" 或 "glb" 并填入 model_url。
 *  例：{ actor_id:"judge", mode:"vrm", model_url:"/hearing-3d/models/judge.vrm", ... }
 */
export const CHARACTER_ASSETS: Record<string, CharacterAsset> = {
  judge:             { actor_id:"judge",             mode:"sprite", sprite_url:"/hearing-3d/reference/char-9-web.jpg" },
  clerk:             { actor_id:"clerk",             mode:"sprite", sprite_url:"/hearing-3d/reference/char-6-web.jpg" },
  plaintiff_counsel: { actor_id:"plaintiff_counsel", mode:"sprite", sprite_url:"/hearing-3d/reference/char-1-web.jpg" },
  plaintiff_party:   { actor_id:"plaintiff_party",   mode:"sprite", sprite_url:"/hearing-3d/reference/char-1-web.jpg" },
  defendant_counsel: { actor_id:"defendant_counsel", mode:"sprite", sprite_url:"/hearing-3d/reference/char-4-web.jpg" },
  defendant_party:   { actor_id:"defendant_party",   mode:"sprite", sprite_url:"/hearing-3d/reference/char-3-web.jpg" },
  interpreter:       { actor_id:"interpreter",       mode:"sprite", sprite_url:"/hearing-3d/reference/char-5-web.jpg" },
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
