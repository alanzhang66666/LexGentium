"use client"

import { useMemo, useRef } from "react"
import { Html } from "@react-three/drei"
import { useFrame, useLoader } from "@react-three/fiber"
import { Box3, Mesh, MeshStandardMaterial, NoColorSpace, Object3D, SRGBColorSpace, TextureLoader, Vector2, Vector3 } from "three"
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js"
import type { ActorMode, CastMember } from "./contracts"
import type { CharacterAsset } from "./asset-adapter"

const TARGET_HEIGHT = 1.62

const FACING: Record<string, number> = {
  // 供应商 OBJ 的正面为本地 +Z，与程序化人偶的 -Z 约定相反。
  judge: Math.PI,
  clerk: 0,
  plaintiff_counsel: Math.PI / 2,
  plaintiff_party: Math.PI / 2,
  defendant_counsel: -Math.PI / 2,
  defendant_party: -Math.PI / 2,
  interpreter: -Math.PI / 2,
  prosecutor: 0,
  fact_witness: 0,
}

/** Static supplier OBJ with explicit PBR bindings and a small whole-body motion cue. */
export function ObjCharacterModel({
  member,
  mode,
  isSpeaking,
  asset,
}: {
  member: CastMember
  mode: ActorMode
  isSpeaking?: boolean
  asset: CharacterAsset
}) {
  if (!asset.model_url || !asset.texture_urls) throw new Error(`角色 ${member.actor_id} 缺少 OBJ/PBR 资产配置`)

  const source = useLoader(OBJLoader, asset.model_url)
  const [baseColor, metallic, roughness, normal] = useLoader(TextureLoader, [
    asset.texture_urls.base_color,
    asset.texture_urls.metallic,
    asset.texture_urls.roughness,
    asset.texture_urls.normal,
  ])
  const motionRef = useRef<Object3D>(null)

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
          name: `hearing-role-${member.actor_id}-${material.name || "material"}`,
          map: baseColor,
          metalnessMap: metallic,
          roughnessMap: roughness,
          normalMap: normal,
          metalness: 0.3,
          roughness: 0.7,
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
      height: Math.max(bounds.max.y - bounds.min.y, 0.001),
    }
  }, [baseColor, member.actor_id, metallic, normal, roughness, source])

  const [x, y, z] = member.position
  const facing = FACING[member.actor_id] ?? 0
  // Supplier files use different miniature unit scales. Normalize them to a
  // consistent human height before placing them in the procedural room.
  const scale = member.scale * (asset.scale ?? 1) * (TARGET_HEIGHT / prepared.height)
  const labelY = TARGET_HEIGHT + 0.18

  useFrame((frameState) => {
    if (!motionRef.current) return
    const t = frameState.clock.getElapsedTime()
    motionRef.current.position.y = Math.sin(t * 1.4 + member.position[0]) * 0.008
    motionRef.current.rotation.y = mode === "talk" ? Math.sin(t * 1.8) * 0.035 : 0
    motionRef.current.rotation.x = mode === "nod" ? Math.sin(t * 5.2) * 0.04 : 0
    motionRef.current.scale.setScalar(scale * (isSpeaking ? 1 + Math.sin(t * 3) * 0.006 : 1))
  })

  return (
    <group position={[x, y - 0.45, z]} rotation={[0, facing, 0]}>
      <group ref={motionRef} scale={scale}>
        <primitive
          object={prepared.object}
          position={[-prepared.center.x, -prepared.minY, -prepared.center.z]}
        />
      </group>
      <Html position={[0, labelY, 0]} center distanceFactor={8}>
        <div className="pointer-events-none flex items-center gap-1.5 whitespace-nowrap rounded-md border border-cyan-200/25 bg-slate-950/88 px-1.5 py-0.5 text-center shadow-md shadow-black/25 backdrop-blur">
          <span className="text-[8px] font-medium tracking-wide text-white/80">{member.label}</span>
          <span className="text-[9px] font-semibold text-cyan-100">{member.name}</span>
          {(mode === "talk" || isSpeaking) && <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />}
        </div>
      </Html>
    </group>
  )
}
