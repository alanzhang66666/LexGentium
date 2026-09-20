import type { Metadata } from "next"
import { Hearing3DExperienceLoader } from "@/components/hearing-3d/Hearing3DExperienceLoader"
import { WorkbenchShell } from "@/components/shell"

export const metadata: Metadata = {
  title: "观庭 · 国际商事仲裁研究平台",
  description: "法序智演 LexGentium 国际商事仲裁 3D 观庭，支持会话记录、角色状态、争点材料与自动镜头联动。",
}

export default function Hearing3DPage() {
  return (
    <WorkbenchShell footer={false}>
      <Hearing3DExperienceLoader />
    </WorkbenchShell>
  )
}
