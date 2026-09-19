import { spawn, type ChildProcess } from "node:child_process"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

// Managed backend harness for one-shot Playwright E2E (Task 11.2).
// Spawns the real FastAPI process on an isolated port with an isolated
// runtime data root and a deterministic mock LLM provider; no manually
// started or watch-mode servers are required.

export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 8017)
export const BACKEND_BASE = `http://127.0.0.1:${BACKEND_PORT}`
const STATE_DIR = join(__dirname, "..", ".runtime")
const STATE_FILE = join(STATE_DIR, "state.json")

export interface BackendHandle {
  pid: number
  dataRoot: string
  baseUrl: string
  transcript: string[]
}

function envForBackend(dataRoot: string): NodeJS.ProcessEnv {
  return {
    ...process.env,
    API_PORT: String(BACKEND_PORT),
    API_TOKEN: "e2e-token",
    RUNTIME_DATA_ROOT: dataRoot,
    CONVERSATION_DB_PATH: join(dataRoot, "conversations.sqlite3"),
    EVALUATION_TASK_DB: join(dataRoot, "app_state.sqlite3"),
    EVALUATION_PROVENANCE_DB: join(dataRoot, "app_state.sqlite3"),
    OPERATION_DB_PATH: join(dataRoot, "operations.sqlite3"),
    HEARING_CHECKPOINT_PATH: join(dataRoot, "checkpoints.sqlite3"),
    GAME_SESSION_DB_PATH: join(dataRoot, "game_sessions.sqlite3"),
    LLM_CACHE: "0",
    // Provider stub: deterministic mock LLM; absent key would exercise the
    // degraded path instead (fault injection via E2E_LLM_MOCK=0).
    E2E_LLM_MOCK: process.env.E2E_LLM_MOCK === "0" ? "" : "1",
    LLM_API_KEY: process.env.E2E_LLM_MOCK === "0" ? "" : process.env.LLM_API_KEY ?? "e2e-stub",
  }
}

async function waitReady(url: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  let lastError = ""
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${url}/health/live`)
      if (res.ok) return
      lastError = `status ${res.status}`
    } catch (err) {
      lastError = String(err)
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error(`backend not ready within ${timeoutMs}ms: ${lastError}`)
}

export async function startBackend(): Promise<BackendHandle> {
  const dataRoot = mkdtempSync(join(tmpdir(), "lexgentium-e2e-"))
  const transcript: string[] = []
  const python = process.env.E2E_BACKEND_PYTHON || "python"
  const child: ChildProcess = spawn(python, ["api_server.py"], {
    cwd: join(__dirname, "..", ".."),
    env: envForBackend(dataRoot),
    stdio: ["ignore", "pipe", "pipe"],
  })
  child.stdout?.on("data", (d) => transcript.push(`stdout: ${String(d).trim()}`))
  child.stderr?.on("data", (d) => transcript.push(`stderr: ${String(d).trim()}`))
  child.on("exit", (code) => transcript.push(`exit: ${code}`))

  try {
    await waitReady(BACKEND_BASE, 60_000)
  } catch (err) {
    child.kill("SIGTERM")
    throw new Error(
      `${String(err)}\ntranscript:\n${transcript.slice(-40).join("\n")}`,
    )
  }

  const handle: BackendHandle = {
    pid: child.pid ?? -1,
    dataRoot,
    baseUrl: BACKEND_BASE,
    transcript,
  }
  mkdirSync(STATE_DIR, { recursive: true })
  writeFileSync(
    STATE_FILE,
    JSON.stringify({ pid: child.pid, dataRoot, baseUrl: BACKEND_BASE }, null, 2),
  )
  return handle
}

export function readBackendState(): { pid: number; dataRoot: string; baseUrl: string } | null {
  if (!existsSync(STATE_FILE)) return null
  try {
    return JSON.parse(readFileSync(STATE_FILE, "utf-8"))
  } catch {
    return null
  }
}

/** 编排式 backend restart：kill 既有进程并以新隔离 data root 重启。 */
export async function restartBackend(): Promise<BackendHandle> {
  const state = readBackendState()
  if (state?.pid && state.pid > 0) {
    try {
      process.kill(state.pid)
    } catch {
      // already exited
    }
  }
  return startBackend()
}

export async function stopBackend(evidence: Record<string, unknown> = {}): Promise<void> {
  const state = readBackendState()
  if (state?.pid && state.pid > 0) {
    try {
      process.kill(state.pid)
    } catch {
      // already exited
    }
  }
  if (state?.dataRoot) {
    try {
      rmSync(state.dataRoot, { recursive: true, force: true })
    } catch {
      // best-effort cleanup
    }
  }
  mkdirSync(STATE_DIR, { recursive: true })
  writeFileSync(
    join(STATE_DIR, "evidence.json"),
    JSON.stringify(
      {
        backend: state,
        finished_at: new Date().toISOString(),
        ...evidence,
      },
      null,
      2,
    ),
  )
  if (existsSync(STATE_FILE)) rmSync(STATE_FILE, { force: true })
}
