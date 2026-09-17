import type { Metadata } from "next"
import { Hearing3DExperience } from "@/components/hearing-3d/Hearing3DExperience"
import { WorkbenchShell } from "@/components/shell"

export const metadata: Metadata = {
  title: "仲裁听证 3D · 法序智演 LexGentium",
  description: "LexGentium 3D 观庭（程序化占位 Phase A）。可挂本场 session，非正式 VRM。",
}

export default function Hearing3DPage() {
  return (
    <WorkbenchShell footer={false}>
      <Hearing3DExperience />
    </WorkbenchShell>
  )
}
