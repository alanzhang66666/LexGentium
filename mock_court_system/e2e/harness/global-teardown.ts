import { stopBackend } from "./backend"

export default async function globalTeardown() {
  await stopBackend()
}
