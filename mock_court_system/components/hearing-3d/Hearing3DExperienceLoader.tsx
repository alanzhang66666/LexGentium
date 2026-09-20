"use client"

import dynamic from "next/dynamic"

export const Hearing3DExperienceLoader = dynamic(
  () => import("./Hearing3DExperience").then((mod) => mod.Hearing3DExperience),
  {
    ssr: false,
    loading: () => (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        正在加载观庭…
      </div>
    ),
  },
)
