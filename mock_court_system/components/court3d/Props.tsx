"use client"

export function SeatProps({ names }: { names: string[] }) {
  return (
    <group>
      {names.includes("case_file_zh") || names.includes("case_file_bilingual") ? (
        <mesh position={[0.22, 0.78, 0.12]} rotation={[0, 0.2, 0]}>
          <boxGeometry args={[0.22, 0.03, 0.28]} />
          <meshStandardMaterial color="#d8c48a" />
        </mesh>
      ) : null}
      {names.includes("pen_silver") || names.includes("pen_dark") ? (
        <mesh position={[0.34, 0.8, 0.02]} rotation={[0, 0, 0.4]}>
          <cylinderGeometry args={[0.012, 0.012, 0.16, 8]} />
          <meshStandardMaterial color={names.includes("pen_silver") ? "#c0c6cc" : "#222"} metalness={0.5} />
        </mesh>
      ) : null}
      {names.includes("keyboard") ? (
        <mesh position={[0, 0.74, 0.08]}>
          <boxGeometry args={[0.32, 0.03, 0.14]} />
          <meshStandardMaterial color="#1c1c1c" />
        </mesh>
      ) : null}
      {names.includes("mic_slim") ? (
        <mesh position={[-0.28, 0.95, 0.1]}>
          <cylinderGeometry args={[0.015, 0.02, 0.28, 8]} />
          <meshStandardMaterial color="#333" />
        </mesh>
      ) : null}
      {names.includes("earpiece_single") ? (
        <mesh position={[0.12, 1.58, 0.08]}>
          <sphereGeometry args={[0.035, 10, 10]} />
          <meshStandardMaterial color="#111" />
        </mesh>
      ) : null}
      {names.includes("folder_tabs") || names.includes("contract_en") ? (
        <mesh position={[-0.18, 0.77, 0.1]} rotation={[0, -0.15, 0]}>
          <boxGeometry args={[0.2, 0.025, 0.26]} />
          <meshStandardMaterial color="#8aa4c8" />
        </mesh>
      ) : null}
    </group>
  )
}
