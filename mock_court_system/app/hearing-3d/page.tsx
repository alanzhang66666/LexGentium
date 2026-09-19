import type { Metadata } from "next"
import { Hearing3DExperience } from "@/components/hearing-3d/Hearing3DExperience"
import { WorkbenchShell } from "@/components/shell"

export const metadata: Metadata = {
  title: "观庭 · 国际商事仲裁研究平台",
  description: "法序智演 LexGentium 3D 观庭（供应商 OBJ 角色资产与 PBR 贴图，程序化人物作 fallback）。可挂本场 session。",
}

export default function Hearing3DPage() {
  return (
    <WorkbenchShell footer={false}>
      <Hearing3DExperience />
    </WorkbenchShell>
  )
}
