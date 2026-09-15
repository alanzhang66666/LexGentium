"use client"

import { Text } from "@react-three/drei"
import type { RoomId } from "@/lib/court3d/protocol"

export function CourtroomStage({ room, evidenceLit }: { room: RoomId; evidenceLit: boolean }) {
  if (room === "lawyer_office") return <OfficeRoom />
  if (room === "mediation") return <MediationRoom />
  return <TrialRoom evidenceLit={evidenceLit} />
}

function TrialRoom({ evidenceLit }: { evidenceLit: boolean }) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 2]} receiveShadow>
        <planeGeometry args={[18, 16]} />
        <meshStandardMaterial color="#3a332c" />
      </mesh>
      <mesh position={[0, 3.4, 8.4]} receiveShadow>
        <boxGeometry args={[16, 6.8, 0.3]} />
        <meshStandardMaterial color="#4a3f35" />
      </mesh>
      <mesh position={[0, 4.55, 8.15]}>
        <circleGeometry args={[0.42, 32]} />
        <meshStandardMaterial color="#c9a227" metalness={0.4} roughness={0.35} />
      </mesh>
      <Text position={[0, 5.15, 8.16]} fontSize={0.18} color="#e8d48b">
        中华人民共和国
      </Text>

      <Desk position={[0, 0.55, 7.15]} width={4.6} depth={1.15} height={0.85} />
      <Desk position={[0, 0.28, 5.2]} width={2.2} depth={0.85} height={0.72} />
      <Desk position={[-3.75, 0.28, 1.85]} width={2.6} depth={1.05} height={0.72} />
      <Desk position={[3.75, 0.28, 1.85]} width={2.6} depth={1.05} height={0.72} />
      <Desk position={[2.35, 0.22, 2.95]} width={1.15} depth={0.7} height={0.64} />

      <mesh position={[0, 0.18, 3.55]}>
        <boxGeometry args={[12, 0.36, 0.12]} />
        <meshStandardMaterial color="#2c261f" />
      </mesh>

      <mesh position={[0, 1.55, 6.35]}>
        <boxGeometry args={[1.7, 0.95, 0.08]} />
        <meshStandardMaterial
          color={evidenceLit ? "#d7e7ff" : "#1a2230"}
          emissive={evidenceLit ? "#7aa7ff" : "#000000"}
          emissiveIntensity={evidenceLit ? 0.55 : 0}
        />
      </mesh>
      <Text position={[-3.75, 1.15, 1.3]} fontSize={0.16} color="#d8c39a">
        原告席
      </Text>
      <Text position={[3.75, 1.15, 1.3]} fontSize={0.16} color="#d8c39a">
        被告席
      </Text>
      <Text position={[0, 1.55, 7.6]} fontSize={0.14} color="#d8c39a">
        审判席
      </Text>

      <mesh position={[0, 0.9, -4.4]} receiveShadow>
        <boxGeometry args={[10, 0.45, 1.6]} />
        <meshStandardMaterial color="#2f2923" />
      </mesh>
    </group>
  )
}

function OfficeRoom() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color="#5b5348" />
      </mesh>
      <mesh position={[0, 2.4, -3.2]}>
        <boxGeometry args={[10, 4.8, 0.2]} />
        <meshStandardMaterial color="#d9d0c3" />
      </mesh>
      <Desk position={[0, 0.28, 0.5]} width={2.8} depth={1.2} height={0.72} />
    </group>
  )
}

function MediationRoom() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color="#4a433b" />
      </mesh>
      <mesh position={[0, 0.38, 0.2]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[1.45, 32]} />
        <meshStandardMaterial color="#6b5340" />
      </mesh>
    </group>
  )
}

function Desk({
  position,
  width,
  depth,
  height,
}: {
  position: [number, number, number]
  width: number
  depth: number
  height: number
}) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={[width, height, depth]} />
      <meshStandardMaterial color="#5c4634" roughness={0.55} />
    </mesh>
  )
}
