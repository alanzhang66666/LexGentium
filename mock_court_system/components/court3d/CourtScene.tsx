"use client"

import { Canvas } from "@react-three/fiber"
import { OrbitControls } from "@react-three/drei"
import { Avatar } from "@/components/court3d/Avatar"
import { CameraDirector } from "@/components/court3d/CameraDirector"
import { CourtroomStage } from "@/components/court3d/CourtroomStage"
import type { CastDefinition, SkinId } from "@/lib/court3d/cast"
import type { PerformanceState } from "@/lib/court3d/performanceStore"
import { ACTORS, SEAT_OF_ACTOR } from "@/lib/court3d/protocol"
import { COURTROOM_SEATS, MEDIATION_SEATS, OFFICE_SEATS } from "@/lib/court3d/seats"

export function CourtScene({
  cast,
  skin,
  state,
}: {
  cast: CastDefinition
  skin: SkinId
  state: PerformanceState
}) {
  const seats = state.room === "lawyer_office" ? OFFICE_SEATS : state.room === "mediation" ? MEDIATION_SEATS : COURTROOM_SEATS
  const visible = visibleActors(state.room, cast)

  return (
    <Canvas shadows camera={{ position: [0, 3.6, -6.4], fov: 42 }} className="h-full w-full">
      <color attach="background" args={["#1b1814"]} />
      <hemisphereLight args={["#fff4e0", "#2a241c", 0.7]} />
      <directionalLight position={[4, 8, -2]} intensity={1.15} castShadow />
      <ambientLight intensity={0.25} />
      <CourtroomStage room={state.room} evidenceLit={state.evidenceLit} />
      {visible.map((actor) => {
        const role = cast.roles[actor]
        const pose = seats[SEAT_OF_ACTOR[actor]]
        const look = seats[SEAT_OF_ACTOR[state.cameraFocus]]?.position
        return (
          <Avatar
            key={actor}
            actor={actor}
            role={role}
            skin={skin}
            pose={pose}
            runtime={state.actors[actor]}
            lookTarget={state.actors[actor].speaking ? undefined : look}
          />
        )
      })}
      <CameraDirector shot={state.cameraShot} focus={state.cameraFocus} room={state.room} />
      <OrbitControls enablePan={false} maxPolarAngle={Math.PI / 2.05} minDistance={2.2} maxDistance={14} />
    </Canvas>
  )
}

function visibleActors(room: PerformanceState["room"], cast: CastDefinition) {
  if (room === "lawyer_office") {
    return ACTORS.filter((a) => a === "plaintiff_counsel" || a === "plaintiff_party" || a === "defendant_counsel" || a === "defendant_party")
  }
  return ACTORS.filter((a) => Boolean(cast.roles[a]))
}
