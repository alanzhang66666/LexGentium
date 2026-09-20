"use client"

import { Canvas } from "@react-three/fiber"
import { ACESFilmicToneMapping } from "three"
import type { SceneState } from "./contracts"
import { ProceduralRoom } from "./ProceduralRoom"
import { CastLayer } from "./CastLayer"
import { CameraDirector, type CameraMode } from "./CameraDirector"
import { castManifest } from "./cast-manifest"

export function Hearing3DScene({ state, cameraMode, automatic = false }: { state: SceneState; cameraMode: CameraMode; automatic?: boolean }) {
  return (
    <div className="h-full min-h-[560px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
      <Canvas
        shadows="soft"
        camera={{ position: [0, 2.65, -7.8], fov: 36 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, toneMapping: ACESFilmicToneMapping, toneMappingExposure: 1.05 }}
        fallback={<div className="p-8 text-white">当前浏览器不支持 WebGL，字幕和事件仍可继续。</div>}
      >
        <ProceduralRoom />
        <CastLayer members={castManifest} actorModes={state.actor_modes} activeActorId={state.active_actor_id} isSpeaking={state.active_actor_id} />
        <CameraDirector state={state} mode={cameraMode} automatic={automatic} />
      </Canvas>
    </div>
  )
}
