"use client"

const PALETTE = {
  floor: "#a8a29e",
  wall: "#e8e4de",
  wallAccent: "#d4cec6",
  deskWoodDark: "#b09a7d",
  deskTop: "#d4bfa0",
  chair: "#6b7280",
  chairDark: "#4b5563",
  screen: "#0f172a",
  screenGlow: "#1e3a5f",
  ceiling: "#f5f5f4",
  ceilingLight: "#fefce8",
  glass: "#e0e7ff",
  plantPot: "#57534e",
  plantLeaf: "#44403c",
}

function Desk({ x, z, width, depth }: { x: number; z: number; width: number; depth: number }) {
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.75, 0]}>
        <boxGeometry args={[width, 0.04, depth]} />
        <meshStandardMaterial color={PALETTE.deskTop} />
      </mesh>
      <mesh position={[-width / 2 + 0.03, 0.375, 0]}>
        <boxGeometry args={[0.06, 0.75, depth]} />
        <meshStandardMaterial color={PALETTE.deskWoodDark} />
      </mesh>
      <mesh position={[width / 2 - 0.03, 0.375, 0]}>
        <boxGeometry args={[0.06, 0.75, depth]} />
        <meshStandardMaterial color={PALETTE.deskWoodDark} />
      </mesh>
      <mesh position={[0, 0.4, -depth / 2 + 0.02]}>
        <boxGeometry args={[width, 0.72, 0.03]} />
        <meshStandardMaterial color={PALETTE.deskWoodDark} />
      </mesh>
      <mesh position={[width * 0.15, 0.82, 0]} rotation={[0, 0, -0.3]}>
        <cylinderGeometry args={[0.008, 0.008, 0.18, 6]} />
        <meshStandardMaterial color="#333333" />
      </mesh>
      <mesh position={[width * 0.15 + 0.03, 0.91, 0]}>
        <sphereGeometry args={[0.02, 6, 6]} />
        <meshStandardMaterial color="#222222" />
      </mesh>
    </group>
  )
}

function Chair({ x, z, rotation = 0 }: { x: number; z: number; rotation?: number }) {
  return (
    <group position={[x, 0, z]} rotation={[0, rotation, 0]}>
      <mesh position={[0, 0.45, 0]}>
        <boxGeometry args={[0.5, 0.06, 0.5]} />
        <meshStandardMaterial color={PALETTE.chair} />
      </mesh>
      <mesh position={[0, 0.75, 0.22]}>
        <boxGeometry args={[0.46, 0.6, 0.06]} />
        <meshStandardMaterial color={PALETTE.chairDark} />
      </mesh>
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.04, 0.06, 0.45, 8]} />
        <meshStandardMaterial color="#333333" />
      </mesh>
    </group>
  )
}

function DeskProp({ x, y, z, width, height, color }: { x: number; y: number; z: number; width: number; height: number; color: string }) {
  return (
    <mesh position={[x, y, z]}>
      <boxGeometry args={[width, height, 0.01]} />
      <meshStandardMaterial color={color} />
    </mesh>
  )
}

export function ProceduralRoom() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color={PALETTE.floor} />
      </mesh>

      <mesh position={[0, 1.6, 4]}>
        <boxGeometry args={[10, 3.2, 0.12]} />
        <meshStandardMaterial color={PALETTE.wall} />
      </mesh>
      <mesh position={[-5, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <boxGeometry args={[8, 3.2, 0.12]} />
        <meshStandardMaterial color={PALETTE.wallAccent} />
      </mesh>
      <mesh position={[5, 1.6, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <boxGeometry args={[8, 3.2, 0.12]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.4} />
      </mesh>
      <mesh position={[0, 3.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color={PALETTE.ceiling} />
      </mesh>
      <mesh position={[0, 3.18, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[6, 2]} />
        <meshBasicMaterial color={PALETTE.ceilingLight} />
      </mesh>

      <Desk x={0} z={1.8} width={3} depth={0.8} />
      <Desk x={-2.1} z={-0.65} width={0.8} depth={4.5} />
      <Desk x={2.1} z={-0.65} width={0.8} depth={4.5} />
      <Desk x={-0.9} z={1} width={1.2} depth={0.5} />

      <Chair x={0} z={3.08} />
      <Chair x={-0.9} z={-0.03} rotation={Math.PI} />
      <Chair x={-3.18} z={0.65} rotation={-Math.PI / 2} />
      <Chair x={-3.18} z={-1.15} rotation={-Math.PI / 2} />
      <Chair x={3.18} z={0.65} rotation={Math.PI / 2} />
      <Chair x={3.18} z={-1.15} rotation={Math.PI / 2} />
      <Chair x={3.18} z={-2.6} rotation={Math.PI / 2} />

      <mesh position={[4.7, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[1.8, 1.02]} />
        <meshBasicMaterial color={PALETTE.screen} />
      </mesh>
      <mesh position={[4.65, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[1.7, 0.92]} />
        <meshBasicMaterial color={PALETTE.screenGlow} />
      </mesh>

      <DeskProp x={-0.5} y={0.78} z={1.8} width={0.3} height={0.04} color="#c4a97d" />
      <DeskProp x={0.5} y={0.78} z={1.8} width={0.22} height={0.02} color="#ffffff" />
      <DeskProp x={-2.1} y={0.78} z={0.5} width={0.22} height={0.02} color="#ffffff" />
      <DeskProp x={2.1} y={0.78} z={0.5} width={0.22} height={0.02} color="#ffffff" />
      <DeskProp x={-0.9} y={0.78} z={1} width={0.25} height={0.02} color="#2d2d2d" />

      <group position={[-4.2, 0, -3.2]}>
        <mesh position={[0, 0.2, 0]}>
          <cylinderGeometry args={[0.15, 0.12, 0.4, 8]} />
          <meshStandardMaterial color={PALETTE.plantPot} />
        </mesh>
        <mesh position={[0, 0.8, 0]}>
          <sphereGeometry args={[0.35, 8, 6]} />
          <meshStandardMaterial color={PALETTE.plantLeaf} />
        </mesh>
      </group>

      <ambientLight intensity={2} />
      <directionalLight position={[0, 6, -4]} intensity={2.4} />
      <directionalLight position={[-4, 4, 2]} intensity={1.2} color="#fef3c7" />
      <pointLight position={[0, 3, 0]} intensity={1.5} color={PALETTE.ceilingLight} distance={8} />
    </group>
  )
}
