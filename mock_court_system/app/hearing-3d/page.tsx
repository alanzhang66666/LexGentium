import type { Metadata } from "next"
import { Hearing3DExperience } from "@/components/hearing-3d/Hearing3DExperience"

export const metadata: Metadata = {
  title: "仲裁听证 3D · LexGentium",
  description: "LexGentium 仲裁听证 3D 技术闭环 Demo（程序化占位资产与人工结构样例）。",
}

export default function Hearing3DPage() {
  return <Hearing3DExperience />
}
