"use client"

import { useRef } from "react"
import { useFrame, useThree } from "@react-three/fiber"
import { Vector3 } from "three"
import { COURTROOM_SEATS, MEDIATION_SEATS, OFFICE_SEATS } from "@/lib/court3d/seats"
import type { Actor, CameraShot, RoomId, SeatId } from "@/lib/court3d/protocol"
import { SEAT_OF_ACTOR } from "@/lib/court3d/protocol"

const SHOT_OFFSET: Record<CameraShot, [number, number, number]> = {
  wide: [0, 3.4, -6.2],
  over_shoulder: [1.15, 1.7, -1.8],
  close_up: [0.15, 1.55, -1.35],
  two_shot: [0, 2.2, -3.4],
}

export function CameraDirector({
  shot,
  focus,
  room,
}: {
  shot: CameraShot
  focus: Actor
  room: RoomId
}) {
  const { camera } = useThree()
  const desired = useRef(new Vector3())
  const look = useRef(new Vector3())

  useFrame((_, delta) => {
    const seats = room === "lawyer_office" ? OFFICE_SEATS : room === "mediation" ? MEDIATION_SEATS : COURTROOM_SEATS
    const seatId = SEAT_OF_ACTOR[focus] as SeatId
    const seat = seats[seatId]
    const off = SHOT_OFFSET[shot]
    if (room === "courtroom" && shot === "wide") {
      desired.current.set(0, 3.6, -6.4)
      look.current.set(0, 1.3, 5.2)
    } else {
      desired.current.set(seat.position[0] + off[0], seat.position[1] + off[1], seat.position[2] + off[2])
      look.current.set(seat.position[0], seat.position[1] + 1.35, seat.position[2])
    }
    const t = 1 - Math.pow(0.001, delta)
    camera.position.lerp(desired.current, t)
    camera.lookAt(look.current)
  })
  return null
}
