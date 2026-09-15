import { redirect } from "next/navigation"

export default async function Court3dSessionRedirect({
  params,
}: {
  params: Promise<{ sessionId: string }> | { sessionId: string }
}) {
  const { sessionId } = await Promise.resolve(params)
  redirect(`/hearing-3d?sessionId=${encodeURIComponent(sessionId)}`)
}
