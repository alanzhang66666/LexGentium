"use client"

import { useMemo } from "react"

/** 从全景渲染图匹配的色板 */
const PALETTE = {
  floor: "#737d8b",
  floor_inset: "#657184",
  aisle: "#8893a2",
  wall: "#dfe5eb",
  wall_accent: "#bdc8d4",
  back_panel: "#26364a",
  back_panel_inner: "#334a62",
  accent: "#65c9d9",
  desk_wood: "#c6ae8d",
  desk_wood_dark: "#b09a7d",
  desk_top: "#d4bfa0",
  chair: "#475569",
  chair_dark: "#273449",
  screen: "#0f172a",
  screen_glow: "#1e3a5f",
  ceiling: "#f5f5f4",
  ceiling_light: "#fefce8",
  glass: "#e0e7ff",
  plant_pot: "#57534e",
  plant_leaf: "#44403c",
}

function Desk({ x, z, w, d, topColor }: { x: number; z: number; w: number; d: number; topColor: string }) {
  const legColor = PALETTE.desk_wood_dark
  return (
    <group position={[x, 0, z]}>
      {/* 桌面 */}
      <mesh position={[0, 0.75, 0]}>
        <boxGeometry args={[w, 0.04, d]} />
        <meshStandardMaterial color={topColor} roughness={0.64} />
      </mesh>
      <mesh position={[0, 0.705, -d / 2 + 0.03]}>
        <boxGeometry args={[w * 0.92, 0.045, 0.035]} />
        <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={0.18} />
      </mesh>
      {/* 侧板 */}
      <mesh position={[-w / 2 + 0.03, 0.375, 0]}>
        <boxGeometry args={[0.06, 0.75, d]} />
        <meshStandardMaterial color={legColor} />
      </mesh>
      <mesh position={[w / 2 - 0.03, 0.375, 0]}>
        <boxGeometry args={[0.06, 0.75, d]} />
        <meshStandardMaterial color={legColor} />
      </mesh>
      {/* 前挡板 */}
      <mesh position={[0, 0.4, -d / 2 + 0.02]}>
        <boxGeometry args={[w, 0.72, 0.03]} />
        <meshStandardMaterial color={legColor} roughness={0.76} />
      </mesh>
      {/* 话筒 */}
      <mesh position={[w * 0.15, 0.82, 0]} rotation={[0, 0, -0.3]}>
        <cylinderGeometry args={[0.008, 0.008, 0.18, 6]} />
        <meshStandardMaterial color="#333" />
      </mesh>
      <mesh position={[w * 0.15 + 0.03, 0.91, 0]}>
        <sphereGeometry args={[0.02, 6, 6]} />
        <meshStandardMaterial color="#222" />
      </mesh>
    </group>
  )
}

function Chair({ x, z, rotation }: { x: number; z: number; rotation?: number }) {
  return (
    <group position={[x, 0, z]} rotation={[0, rotation ?? 0, 0]}>
      <mesh position={[0, 0.45, 0]}>
        <boxGeometry args={[0.5, 0.06, 0.5]} />
        <meshStandardMaterial color={PALETTE.chair} />
      </mesh>
      <mesh position={[0, 0.75, 0.22]}>
        <boxGeometry args={[0.46, 0.6, 0.06]} />
        <meshStandardMaterial color={PALETTE.chair_dark} />
      </mesh>
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.04, 0.06, 0.45, 8]} />
        <meshStandardMaterial color="#333" />
      </mesh>
    </group>
  )
}

function DeskProp({ x, y, z, w, h, color, label }: { x: number; y: number; z: number; w: number; h: number; color: string; label?: string }) {
  return (
    <mesh position={[x, y, z]}>
      <boxGeometry args={[w, h, 0.01]} />
      <meshStandardMaterial color={color} />
    </mesh>
  )
}

export function ProceduralRoom() {
  return (
    <group>
      {/* 地毯 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color={PALETTE.floor} roughness={0.9} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.006, 0.35]}>
        <planeGeometry args={[8.8, 6.9]} />
        <meshStandardMaterial color={PALETTE.floor_inset} roughness={0.96} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, -0.3]}>
        <planeGeometry args={[1.15, 6.9]} />
        <meshStandardMaterial color={PALETTE.aisle} roughness={0.92} />
      </mesh>

      {/* 后墙 */}
      <mesh position={[0, 1.6, 4]}>
        <boxGeometry args={[10, 3.2, 0.12]} />
        <meshStandardMaterial color={PALETTE.wall} roughness={0.88} />
      </mesh>
      {/* 后墙视觉中心：压住空白墙面，同时让首席席位成为画面锚点。 */}
      <mesh position={[0, 1.7, 3.91]}>
        <boxGeometry args={[6.9, 2.42, 0.08]} />
        <meshStandardMaterial color={PALETTE.back_panel} roughness={0.8} />
      </mesh>
      <mesh position={[0, 1.64, 3.855]}>
        <boxGeometry args={[5.8, 1.76, 0.045]} />
        <meshStandardMaterial color={PALETTE.back_panel_inner} roughness={0.82} />
      </mesh>
      <mesh position={[0, 2.68, 3.82]}>
        <boxGeometry args={[2.7, 0.045, 0.045]} />
        <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={0.28} />
      </mesh>
      <mesh position={[0, 0.72, 3.82]}>
        <boxGeometry args={[4.2, 0.035, 0.045]} />
        <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={0.16} />
      </mesh>
      <mesh position={[-3.55, 1.65, 3.83]}>
        <boxGeometry args={[0.12, 2.25, 0.06]} />
        <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={0.16} />
      </mesh>
      <mesh position={[3.55, 1.65, 3.83]}>
        <boxGeometry args={[0.12, 2.25, 0.06]} />
        <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={0.16} />
      </mesh>
      {/* 左墙 */}
      <mesh position={[-5, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <boxGeometry args={[8, 3.2, 0.12]} />
        <meshStandardMaterial color={PALETTE.wall_accent} />
      </mesh>
      {/* 右墙（带玻璃窗效果） */}
      <mesh position={[5, 1.6, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <boxGeometry args={[8, 3.2, 0.12]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.4} />
      </mesh>

      {/* 天花板 */}
      <mesh position={[0, 3.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color={PALETTE.ceiling} />
      </mesh>
      {/* 顶灯带 */}
      <mesh position={[0, 3.18, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[6, 2]} />
        <meshBasicMaterial color={PALETTE.ceiling_light} />
      </mesh>
      <mesh position={[-2.5, 3.14, 0.4]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.4, 0.32]} />
        <meshBasicMaterial color="#dbeafe" />
      </mesh>
      <mesh position={[2.5, 3.14, 0.4]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.4, 0.32]} />
        <meshBasicMaterial color="#dbeafe" />
      </mesh>

      {/* 首席仲裁桌（正对入口） */}
      <Desk x={0} z={1.8} w={3.0} d={0.8} topColor={PALETTE.desk_top} />
      {/* 申请方桌（左侧长桌） */}
      <Desk x={-2.1} z={-0.65} w={0.8} d={4.5} topColor={PALETTE.desk_top} />
      {/* 被申请方桌（右侧长桌） */}
      <Desk x={2.1} z={-0.65} w={0.8} d={4.5} topColor={PALETTE.desk_top} />
      {/* 秘书桌 */}
      <Desk x={-0.9} z={1.0} w={1.2} d={0.5} topColor={PALETTE.desk_top} />

      {/* 九席座椅（与 cast-manifest 席位一致，置于角色身后 ~0.28；Chair 默认朝 -Z） */}
      <Chair x={0} z={3.08} />                              {/* 首席仲裁员，朝 -Z */}
      <Chair x={-0.9} z={-0.03} rotation={Math.PI} />       {/* 仲裁庭秘书，朝 +Z */}
      <Chair x={-3.18} z={0.65} rotation={-Math.PI / 2} />  {/* 申请人代理，朝 +X */}
      <Chair x={-3.18} z={-1.15} rotation={-Math.PI / 2} /> {/* 申请人企业代表 */}
      <Chair x={3.18} z={0.65} rotation={Math.PI / 2} />    {/* 被申请人代理，朝 -X */}
      <Chair x={3.18} z={-1.15} rotation={Math.PI / 2} />   {/* 被申请人企业代表 */}
      <Chair x={3.18} z={-2.6} rotation={Math.PI / 2} />    {/* 口译员 */}
      <Chair x={-4.0} z={-2.35} rotation={Math.PI} />        {/* 公诉人 */}
      <Chair x={4.0} z={-2.35} rotation={Math.PI} />         {/* 外籍事实证人 */}

      {/* 证据屏 */}
      <mesh position={[4.7, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[1.8, 1.02]} />
        <meshBasicMaterial color={PALETTE.screen} />
      </mesh>
      <mesh position={[4.65, 1.6, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[1.7, 0.92]} />
        <meshBasicMaterial color={PALETTE.screen_glow} />
      </mesh>

      {/* 桌面道具：卷宗（首席桌） */}
      <DeskProp x={-0.5} y={0.78} z={1.8} w={0.3} h={0.04} color="#c4a97d" />
      <DeskProp x={0.5} y={0.78} z={1.8} w={0.22} h={0.02} color="#ffffff" />
      {/* 申请方桌面道具 */}
      <DeskProp x={-2.1} y={0.78} z={0.5} w={0.22} h={0.02} color="#ffffff" />
      {/* 被申请方桌面道具 */}
      <DeskProp x={2.1} y={0.78} z={0.5} w={0.22} h={0.02} color="#ffffff" />
      {/* 秘书桌面键盘 */}
      <DeskProp x={-0.9} y={0.78} z={1.0} w={0.25} h={0.02} color="#2d2d2d" />

      {/* 植物（角落） */}
      <group position={[-4.2, 0, -3.2]}>
        <mesh position={[0, 0.2, 0]}>
          <cylinderGeometry args={[0.15, 0.12, 0.4, 8]} />
          <meshStandardMaterial color={PALETTE.plant_pot} />
        </mesh>
        <mesh position={[0, 0.8, 0]}>
          <sphereGeometry args={[0.35, 8, 6]} />
          <meshStandardMaterial color={PALETTE.plant_leaf} />
        </mesh>
      </group>

      {/* 灯光：前侧冷光保证人脸可读，侧面暖光拉出桌体和墙板层次。 */}
      <ambientLight intensity={0.9} />
      <directionalLight castShadow position={[0, 6, -4]} intensity={2.25} shadow-mapSize={[1024, 1024]} shadow-camera-left={-6} shadow-camera-right={6} shadow-camera-top={5} shadow-camera-bottom={-4} />
      <directionalLight position={[-4, 4, 2]} intensity={1.15} color="#fef3c7" />
      <pointLight position={[0, 3, 0]} intensity={1.35} color={PALETTE.ceiling_light} distance={8} />
      <pointLight position={[0, 2.2, 3.4]} intensity={1.1} color="#8be4ef" distance={5} />
    </group>
  )
}
