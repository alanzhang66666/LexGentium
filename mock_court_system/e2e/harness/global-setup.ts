import { startBackend } from "./backend"

export default async function globalSetup() {
  await startBackend()
}
