"use client"

import { Html } from "@react-three/drei"
import { useLoader } from "@react-three/fiber"
import { useMemo } from "react"
import { Box3, Mesh, MeshStandardMaterial, NoColorSpace, Object3D, SRGBColorSpace, TextureLoader, Vector2, Vector3 } from "three"
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js"
import { JUDICIAL_POLICE_ASSET } from "./asset-adapter"

// 入口前侧的开放区域：广角中清晰可见，不占用七席角色的位置。
const DEFAULT_POSITION: [number, number, number] = [1.5, 0, -2.7]

/**
 * Loads the supplied high-poly judicial-police OBJ as a real scene object.
 *
 * The OBJ's MTL only describes legacy diffuse maps. We therefore bind the
 * four delivered PBR maps explicitly so the model renders consistently in
 * Three.js instead of falling back to a flat grey MeshPhongMaterial.
 */
export function JudicialPoliceModel({
  position = DEFAULT_POSITION,
  rotationY = Math.PI,
  scale = JUDICIAL_POLICE_ASSET.scale ?? 1,
}: {
  position?: [number, number, number]
  rotationY?: number
  scale?: number
}) {
  const modelUrl = JUDICIAL_POLICE_ASSET.model_url ?? ""
  const textureUrls = JUDICIAL_POLICE_ASSET.texture_urls
  if (!textureUrls) throw new Error("司法警察 OBJ 资产缺少 PBR 贴图配置")

  const source = useLoader(OBJLoader, modelUrl)
  const [baseColor, metallic, roughness, normal] = useLoader(TextureLoader, [
    textureUrls.base_color,
    textureUrls.metallic,
    textureUrls.roughness,
    textureUrls.normal,
  ])

  const prepared = useMemo(() => {
    baseColor.colorSpace = SRGBColorSpace
    metallic.colorSpace = NoColorSpace
    roughness.colorSpace = NoColorSpace
    normal.colorSpace = NoColorSpace
    baseColor.needsUpdate = true
    metallic.needsUpdate = true
    roughness.needsUpdate = true
    normal.needsUpdate = true

    const object = source.clone(true)
    object.traverse((node: Object3D) => {
      if (!(node instanceof Mesh)) return

      const materials = Array.isArray(node.material) ? node.material : [node.material]
      const pbrMaterials = materials.map((material) => {
        const pbr = new MeshStandardMaterial({
          name: `judicial-police-${material.name || "material"}`,
          map: baseColor,
          metalnessMap: metallic,
          roughnessMap: roughness,
          normalMap: normal,
          metalness: 0.45,
          roughness: 0.72,
        })
        pbr.normalScale = new Vector2(1, 1)
        return pbr
      })

      node.material = Array.isArray(node.material) ? pbrMaterials : pbrMaterials[0]
      node.castShadow = true
      node.receiveShadow = true
    })

    const bounds = new Box3().setFromObject(object)
    return {
      object,
      center: bounds.getCenter(new Vector3()),
      minY: bounds.min.y,
    }
  }, [baseColor, metallic, normal, roughness, source])

  return (
    <group position={position} rotation={[0, rotationY, 0]} scale={scale}>
      <primitive
        object={prepared.object}
        position={[-prepared.center.x, -prepared.minY, -prepared.center.z]}
      />
      <Html position={[0, 1.5, 0]} center>
        <div className="pointer-events-none flex items-center gap-1.5 whitespace-nowrap rounded-md border border-amber-200/30 bg-slate-950/88 px-1.5 py-0.5 text-center shadow-md shadow-black/25 backdrop-blur">
          <span className="text-[8px] font-medium text-white/80">司法警察</span>
          <span className="text-[9px] font-semibold text-amber-100">现场秩序</span>
        </div>
      </Html>
    </group>
  )
}
