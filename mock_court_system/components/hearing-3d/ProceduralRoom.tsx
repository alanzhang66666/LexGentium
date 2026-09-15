"use client"

export function ProceduralRoom() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color="#d6d3d1" />
      </mesh>
      <mesh position={[0, 1.6, 4]}>
        <boxGeometry args={[10, 3.2, 0.12]} />
        <meshStandardMaterial color="#e7e5e4" />
      </mesh>
      <mesh position={[-0.0, 0.8, 2.0]}>
        <boxGeometry args={[3, 0.12, 0.8]} />
        <meshStandardMaterial color="#7c5c45" />
      </mesh>
      <mesh position={[-2.1, 0.8, -0.65]}>
        <boxGeometry args={[0.8, 0.12, 4.5]} />
        <meshStandardMaterial color="#7c5c45" />
      </mesh>
      <mesh position={[2.1, 0.8, -0.65]}>
        <boxGeometry args={[0.8, 0.12, 4.5]} />
        <meshStandardMaterial color="#7c5c45" />
      </mesh>
      <mesh position={[-0.9, 0.8, 1.0]}>
        <boxGeometry args={[1.2, 0.12, 0.5]} />
        <meshStandardMaterial color="#7c5c45" />
      </mesh>
      <mesh position={[4.7, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[1.8, 1.02]} />
        <meshBasicMaterial color="#0f172a" />
      </mesh>
      <ambientLight intensity={1.8} />
      <directionalLight position={[0, 6, -4]} intensity={2.2} />
    </group>
  )
}
