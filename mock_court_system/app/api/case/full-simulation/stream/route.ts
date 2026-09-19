import { proxySse } from "@/lib/backend-stream"

export async function POST(request: Request) {
  return proxySse(request, {
    path: "/case/full-simulation/stream",
    method: "POST",
    label: "full-simulation-stream",
  })
}
