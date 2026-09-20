"use client"

import { useMemo, useRef } from "react"
import { Html } from "@react-three/drei"
import { useFrame, useLoader, useThree } from "@react-three/fiber"
import { Box3, Mesh, NoColorSpace, Object3D, SRGBColorSpace, TextureLoader, Vector3 } from "three"
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js"
import type { ActorMode, CastMember } from "./contracts"
import type { CharacterAsset } from "./asset-adapter"
import { createHearingRoleMaterial, FACE_MATERIAL_PRESET, getStudioEnvMap, softenNormalMap } from "./face-material"

const TARGET_HEIGHT = 1.62

const FACING: Record<string, number> = {
  // 供应商 OBJ 的正面为本地 +Z，与程序化人偶的 -Z 约定相反。
  judge: Math.PI,
  associate_judge: Math.PI,
  people_juror: Math.PI,
  clerk: 0,
  plaintiff_counsel: Math.PI / 2,
  prosecutor: Math.PI / 2,
  china_company_rep: Math.PI / 2,
  defendant_counsel: -Math.PI / 2,
  defendant_party: -Math.PI / 2,
  interpreter: -Math.PI / 2,
  technical_expert_witness: 0,
  fact_witness: 0,
  judicial_police: Math.PI,
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
  const { gl } = useThree()
  const motionRef = useRef<Object3D>(null)

  const prepared = useMemo(() => {
    baseColor.colorSpace = SRGBColorSpace
    metallic.colorSpace = NoColorSpace
    roughness.colorSpace = NoColorSpace
    normal.colorSpace = NoColorSpace

    // Faces occupy small UV islands on the 2K atlas. Keep the highest cheap
    // anisotropic filter the GPU allows so mid-shots stay readable.
    const anisotropy = Math.min(FACE_MATERIAL_PRESET.maxAnisotropy, gl.capabilities.getMaxAnisotropy())
    for (const texture of [baseColor, metallic, roughness, normal]) {
      texture.anisotropy = anisotropy
      texture.needsUpdate = true
    }
    const skinNormal = softenNormalMap(normal)
    const envMap = getStudioEnvMap(gl)

    const object = source.clone(true)
    object.traverse((node: Object3D) => {
      if (!(node instanceof Mesh)) return

      const materials = Array.isArray(node.material) ? node.material : [node.material]
      const pbrMaterials = materials.map((material) => createHearingRoleMaterial({
        name: `hearing-role-${member.actor_id}-${material.name || "material"}`,
        baseColor,
        metallic,
        roughness,
        normal: skinNormal,
        envMap,
      }))
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
  }, [baseColor, gl, member.actor_id, metallic, normal, roughness, source])

  const [x, y, z] = member.position
  const facing = FACING[member.actor_id] ?? 0
  // Supplier files use different miniature unit scales. Normalize them to a
  // consistent human height before placing them in the procedural room.
  const scale = member.scale * (asset.scale ?? 1) * (TARGET_HEIGHT / prepared.height)
  const labelY = TARGET_HEIGHT + 0.18

  useFrame((frameState) => {
    if (!motionRef.current) return
    const t = frameState.clock.getElapsedTime()
    // Whole-body bobbing makes static supplier models look weightless. Keep the
    // silhouette grounded and reserve a restrained lean for active speech.
    motionRef.current.position.y = 0
    motionRef.current.rotation.y = mode === "talk" || isSpeaking ? Math.sin(t * 1.55) * 0.014 : 0
    motionRef.current.rotation.x = mode === "nod" ? Math.sin(t * 4.6) * 0.022 : 0
    motionRef.current.scale.setScalar(scale)
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
