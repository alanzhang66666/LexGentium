import {
  Color,
  MeshPhysicalMaterial,
  NoColorSpace,
  PMREMGenerator,
  Texture,
  Vector2,
  type WebGLRenderer,
} from "three"
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js"
import { FACE_MATERIAL_PRESET } from "./face-material-preset"

export { FACE_MATERIAL_PRESET }

const SHEEN_COLOR = new Color("#e3c2a4")

let envCache: { gl: WebGLRenderer; map: Texture } | null = null

export function getStudioEnvMap(gl: WebGLRenderer): Texture {
  if (envCache?.gl === gl) return envCache.map
  const pmrem = new PMREMGenerator(gl)
  const room = new RoomEnvironment()
  const map = pmrem.fromScene(room, 0.04).texture
  if (typeof room.dispose === "function") room.dispose()
  pmrem.dispose()
  envCache = { gl, map }
  return map
}

export function softenNormalMap(source: Texture): Texture {
  const image = source.image as CanvasImageSource | undefined
  if (!image || typeof document === "undefined") return source
  const width = "width" in image ? Number(image.width) : 0
  const height = "height" in image ? Number(image.height) : 0
  if (!width || !height) return source

  const canvas = document.createElement("canvas")
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext("2d")
  if (!context) return source
  // Scan normals carry 1-pixel sparkle that reads as triangular skin. A short
  // blur keeps pores from becoming mesh facets without inventing new faces.
  context.filter = "blur(0.85px)"
  context.drawImage(image, 0, 0, width, height)
  const softened = source.clone()
  softened.image = canvas
  softened.colorSpace = NoColorSpace
  softened.needsUpdate = true
  return softened
}

export function createHearingRoleMaterial({
  name,
  baseColor,
  metallic,
  roughness,
  normal,
  envMap,
}: {
  name: string
  baseColor: Texture
  metallic: Texture
  roughness: Texture
  normal: Texture
  envMap?: Texture
}): MeshPhysicalMaterial {
  const material = new MeshPhysicalMaterial({
    name,
    map: baseColor,
    metalnessMap: metallic,
    roughnessMap: roughness,
    normalMap: normal,
    metalness: FACE_MATERIAL_PRESET.metalness,
    roughness: FACE_MATERIAL_PRESET.roughness,
    sheen: FACE_MATERIAL_PRESET.sheen,
    sheenRoughness: FACE_MATERIAL_PRESET.sheenRoughness,
    sheenColor: SHEEN_COLOR,
    clearcoat: FACE_MATERIAL_PRESET.clearcoat,
    clearcoatRoughness: FACE_MATERIAL_PRESET.clearcoatRoughness,
    envMap: envMap ?? null,
    envMapIntensity: FACE_MATERIAL_PRESET.envMapIntensity,
    flatShading: false,
  })
  material.normalScale = new Vector2(FACE_MATERIAL_PRESET.normalScale, FACE_MATERIAL_PRESET.normalScale)
  return material
}
