# LexGentium 仲裁听证 3D 第一阶段 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 LexGentium Next.js 应用中交付一个不依赖正式 VRM/GLB 的可运行仲裁听证 3D Demo：程序化仲裁室、七席占位角色、四机位、事件播放、字幕 HUD、争点/材料状态、暂停/跳转和断线基础恢复。

**Architecture:** 3D 页面位于 `/hearing-3d`，所有业务输入先转换为统一 `HearingEvent`，再由纯函数 `sceneReducer` 生成 `SceneState`；Three.js 渲染层只消费 `SceneState`，不读取 CIAgent 或后端内部对象。第一阶段使用交付包中的 JSON 合同和 sample events，正式模型缺失时使用显式标记的程序化占位资产；后续正式 GLB/VRM 只替换 asset adapter。

**Tech Stack:** Next.js 16、React 19、TypeScript、Three.js、`@react-three/fiber`、`@react-three/drei`、Vitest、交付包 v1.1 的 `scene-layout.json`/`cast-manifest.json`/`event-contract.json`/`sample-events.jsonl`。

## Global Constraints

- 首版程序范围固定为仲裁听证，不扩展到其他诉讼程序。
- 正式运行资产尚未交付；任何占位人物、房间和动作必须显示为 placeholder/scripted demo，不能伪装为最终资产。
- 坐标单位使用米；x 向右、y 向上、z 朝向首席仲裁员；坐席参考点是 chair seat center，不是 actor root。
- 运行时必须支持七个 actor_id：`judge`、`clerk`、`plaintiff_counsel`、`plaintiff_party`、`defendant_counsel`、`defendant_party`、`interpreter`。
- 事件顺序使用 `seq`，去重使用 `eventId`；不得以网络到达顺序替代后端顺序。
- 断线或数据缺失时保留已收到的文字和材料，不补造事实、字幕或法律结论。
- 第一阶段不接真实后端推理；通过 sourceType=`scripted_demo` 的样例事件验证完整播放闭环。
- 不把大尺寸参考 PNG 或嵌套 ZIP 放进 Next.js bundle；运行时只复制小型合同 JSON 和必要 SVG。
- 每个任务结束都要运行该任务指定的测试；提交操作由负责 git 的 agent 执行。

---

## 文件边界总览

### 新增

- `app/hearing-3d/page.tsx`：3D 体验页面入口。
- `components/hearing-3d/Hearing3DExperience.tsx`：客户端状态编排和页面布局。
- `components/hearing-3d/Hearing3DScene.tsx`：R3F Canvas 与 3D 场景。
- `components/hearing-3d/ProceduralRoom.tsx`：程序化房间、桌椅、证据屏。
- `components/hearing-3d/PlaceholderCharacter.tsx`：占位人物和动作状态。
- `components/hearing-3d/CastLayer.tsx`：七席角色实例化。
- `components/hearing-3d/CameraDirector.tsx`：四机位与自动导播。
- `components/hearing-3d/HearingHUD.tsx`：阶段、发言人、争点、字幕和来源标记。
- `components/hearing-3d/EventTimeline.tsx`：播放控制、进度、跳转、缺口提示。
- `components/hearing-3d/MaterialPanel.tsx`：材料摘要、版本、锚点和权限状态。
- `components/hearing-3d/contracts.ts`：HearingEvent、CastManifest、SceneState 类型。
- `components/hearing-3d/cast-manifest.ts`：七席 placeholder manifest。
- `components/hearing-3d/event-source.ts`：sample events 加载和未来 adapter 接口。
- `components/hearing-3d/playback-store.ts`：事件游标、去重、排序、断线状态。
- `components/hearing-3d/scene-reducer.ts`：纯函数事件 reducer。
- `components/hearing-3d/scene-reducer.test.ts`：reducer 契约测试。
- `components/hearing-3d/playback-store.test.ts`：播放状态测试。
- `public/hearing-3d/contracts/scene-layout.json`：从交付包规范化复制。
- `public/hearing-3d/contracts/cast-manifest.json`：从交付包复制并补 placeholder 状态。
- `public/hearing-3d/contracts/event-contract.json`：从交付包复制。
- `public/hearing-3d/contracts/sample-events.jsonl`：从交付包复制。
- `public/hearing-3d/README.md`：运行资产状态、事件来源和替换正式资产说明。
- `vitest.config.ts`：前端纯逻辑测试配置（若仓库没有现成配置）。

### 修改

- `package.json`：加入 Three.js/R3F/Drei/Vitest 依赖及 test 脚本。
- `app/layout.tsx`：为 hearing-3d 页面补页面元数据（不改变现有全局品牌）。
- `components/navigation.tsx`：增加仲裁听证 3D 入口链接。
- `README.md`：增加 `/hearing-3d` 第一阶段能力和正式资产未交付说明。
- `docs/superpowers/specs/2026-09-13-lexgentium-hearing-3d-design.md`：在实现完成后回填第一阶段验收结果。

---

### Task 1: 安装 3D 依赖并导入交付合同

**Files:**
- Modify: `package.json`
- Create: `vitest.config.ts`
- Create: `public/hearing-3d/contracts/scene-layout.json`
- Create: `public/hearing-3d/contracts/cast-manifest.json`
- Create: `public/hearing-3d/contracts/event-contract.json`
- Create: `public/hearing-3d/contracts/sample-events.jsonl`
- Create: `public/hearing-3d/README.md`

**Interfaces:**
- Produces static runtime contracts at `/hearing-3d/contracts/*.json` and `/hearing-3d/contracts/sample-events.jsonl`.
- `package.json` scripts must contain `"test:3d": "vitest run components/hearing-3d"`.

- [ ] **Step 1: 从两个 ZIP 解压并核对源文件**

将 v1.1 包中的 `contracts/scene-layout.json`、`contracts/cast-manifest.json`、`contracts/event-contract.json`、`contracts/sample-events.jsonl`复制到 `public/hearing-3d/contracts/`。不复制嵌套 ZIP、角色 PNG 或未验证的正式模型。

- [ ] **Step 2: 补充 placeholder 资产状态**

在运行时 manifest 中保留七个 actor_id，并为每个角色写入 `status: "placeholder"`、`assetKind: "procedural"`、seatId 和交付包坐标。`plaintiff_party` 没有正式参考图，必须写 `referenceAvailable: false`。

- [ ] **Step 3: 安装依赖并定义测试脚本**

使用 `three`、`@react-three/fiber`、`@react-three/drei`、`vitest`。只增加第一阶段需要的依赖，不引入 physics、动画编辑器或大型 UI 框架。

- [ ] **Step 4: 添加资产状态 README**

明确写出：当前为程序化占位房间/角色；正式 GLB/VRM、动作、音频未交付；替换路径是 cast manifest 的 `modelUrl/seatToRoot/forwardAxis/scale`。

- [ ] **Step 5: 验证静态合同**

运行：`npm run test:3d -- --runInBand`。  
预期：合同文件存在、JSON 可解析，尚无 reducer 测试时 Vitest 配置可启动。

---

### Task 2: 定义类型、初始状态和 SceneReducer

**Files:**
- Create: `components/hearing-3d/contracts.ts`
- Create: `components/hearing-3d/cast-manifest.ts`
- Create: `components/hearing-3d/scene-reducer.ts`
- Create: `components/hearing-3d/scene-reducer.test.ts`

**Interfaces:**

```ts
export type HearingEventType =
  | "session_started" | "stage_changed" | "issue_opened"
  | "utterance_committed" | "claim_status_changed"
  | "playback_policy_changed" | "session_finished"

export interface HearingEvent {
  schemaVersion: "1.1"
  eventId: string
  runId: string
  sessionId: string
  seq: number
  type: HearingEventType
  occurredAt: string
  sourceType: "backend_run" | "scripted_demo"
  provenance?: Record<string, unknown>
  issueId?: string | null
  supersedesEventId?: string | null
  payload: Record<string, unknown>
}

export interface SceneState {
  sessionId: string | null
  runId: string | null
  currentSeq: number
  latestSeq: number
  stage: { id: string; label: string } | null
  activeIssue: { id: string; label: string; description?: string } | null
  activeActorId: string | null
  actorModes: Record<string, "idle" | "listen" | "talk" | "nod">
  subtitle: { zh: string; en?: string; actorId?: string } | null
  claims: Record<string, Record<string, unknown>>
  materials: Record<string, Record<string, unknown>>
  playbackPolicy: Record<string, "allow" | "blocked" | "redacted">
  status: "idle" | "playing" | "paused" | "disconnected" | "finished"
  sourceType: "backend_run" | "scripted_demo" | null
}

export function reduceScene(state: SceneState, event: HearingEvent): SceneState
export function createInitialSceneState(): SceneState
```

- [ ] **Step 1: Write failing reducer tests**

Test cases must assert:

```ts
it("initializes session and source on session_started", () => {
  const next = reduceScene(createInitialSceneState(), sessionStarted)
  expect(next.sessionId).toBe("demo-1")
  expect(next.sourceType).toBe("scripted_demo")
  expect(next.status).toBe("playing")
})

it("updates actor and subtitle on utterance_committed", () => {
  const next = reduceScene(stateAfterStart, utterance)
  expect(next.activeActorId).toBe("plaintiff_counsel")
  expect(next.actorModes.plaintiff_counsel).toBe("talk")
  expect(next.subtitle?.zh).toContain("诉讼请求")
})

it("does not apply blocked or duplicate events", () => {
  const blocked = reduceScene(stateAfterPolicyBlocked, blockedUtterance)
  expect(blocked.subtitle).toBeNull()
  expect(reduceScene(blocked, blockedUtterance)).toEqual(blocked)
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm run test:3d -- scene-reducer.test.ts`.  
Expected: FAIL because types/reducer are not implemented.

- [ ] **Step 3: Implement initial state and reducer**

Implement deterministic handlers for all seven event types. `utterance_committed` sets the actor to `talk`, sets all other actors to `listen` or `idle`, stores zh/en subtitle, claim/material references and event sequence. `playback_policy_changed` updates policy without deleting historical state. Blocked/redacted events must not fabricate text.

- [ ] **Step 4: Implement placeholder cast manifest**

Create seven members with `status: "placeholder"`, exact actor IDs, seat IDs, coordinates from the contract, `seatToRoot: [0,0,0]`, `forwardAxis: [0,0,1]`, `scale: 1` and an explicit `assetKind: "procedural"`.

- [ ] **Step 5: Run tests**

Run: `npm run test:3d -- scene-reducer.test.ts`.  
Expected: all reducer tests pass.

---

### Task 3: Implement PlaybackStore and event source

**Files:**
- Create: `components/hearing-3d/playback-store.ts`
- Create: `components/hearing-3d/playback-store.test.ts`
- Create: `components/hearing-3d/event-source.ts`

**Interfaces:**

```ts
export interface PlaybackStore {
  append(events: HearingEvent[]): void
  consumeNext(): HearingEvent | null
  pause(): void
  resume(): void
  jumpTo(seq: number): void
  jumpToLatest(): void
  getCursor(): number
  getLatestSeq(): number
  getPendingGap(): number[]
  getState(): SceneState
}

export function createPlaybackStore(initial?: SceneState): PlaybackStore
export async function loadSampleEvents(url?: string): Promise<HearingEvent[]>
```

- [ ] **Step 1: Write failing store tests**

Cover eventId deduplication, seq sorting, missing gap reporting, pause/resume, jump-to-latest, and a duplicate event arriving after a superseding event.

- [ ] **Step 2: Implement store**

Maintain `Map<eventId,HearingEvent>`, sorted pending events by seq, `currentSeq`, `latestSeq`, paused state, and an applied event set. `consumeNext()` only consumes `currentSeq + 1`; if unavailable but higher seq exists, leave a gap visible. `jumpToLatest()` applies buffered events in order and marks skipped ranges in a `skippedSeqs` internal field used by the timeline.

- [ ] **Step 3: Implement sample event loader**

Use `fetch("/hearing-3d/contracts/sample-events.jsonl")`, parse each non-empty line, validate required common fields, reject invalid lines with a visible error object, and retain sourceType=`scripted_demo`.

- [ ] **Step 4: Run store tests**

Run: `npm run test:3d -- playback-store.test.ts`.  
Expected: all ordering, deduplication and gap tests pass.

---

### Task 4: Build the procedural 3D scene

**Files:**
- Create: `components/hearing-3d/Hearing3DScene.tsx`
- Create: `components/hearing-3d/ProceduralRoom.tsx`
- Create: `components/hearing-3d/PlaceholderCharacter.tsx`
- Create: `components/hearing-3d/CastLayer.tsx`
- Create: `components/hearing-3d/CameraDirector.tsx`

**Interfaces:**

```tsx
<Hearing3DScene
  sceneState={sceneState}
  cameraMode={cameraMode}
  onCameraModeChange={setCameraMode}
/>

<CastLayer members={castManifest} actorModes={sceneState.actorModes} />
<CameraDirector state={sceneState} mode={cameraMode} />
```

- [ ] **Step 1: Implement `ProceduralRoom`**

Use low-cost Three.js boxes/planes for floor, walls, presiding desk, claimant desk, respondent desk, secretary desk, chairs and evidence screen. Load `scene-layout.json` at build/runtime and use its coordinates rather than duplicating positions in components. The front wall is hidden for the wide camera according to `hidden_nodes`.

- [ ] **Step 2: Implement `PlaceholderCharacter`**

Use a low-poly capsule/body/head/shoulder geometry with neutral business colors. Props: `actorId`, `position`, `lookAt`, `mode`, `label`. `talk` uses a small head/torso animation, `listen` rotates target, `nod` performs a short deterministic scale/rotation animation, `idle` remains stable. Render a small “占位” indicator only in debug/provenance mode, not as a visual obstruction.

- [ ] **Step 3: Implement `CastLayer`**

Instantiate exactly seven members from `castManifest`; resolve seat coordinates from scene layout; apply `seatToRoot/forwardAxis/scale`; do not load the reference PNGs as scene textures. If an asset URL later becomes available, use an asset adapter branch without changing the member interface.

- [ ] **Step 4: Implement `CameraDirector`**

Create the four cameras from `scene-layout.json`. Automatic mode selects by active actor/phase; manual mode freezes selection until the user chooses “恢复自动”. Use damped position/target interpolation; never teleport the camera on every event.

- [ ] **Step 5: Add scene fallback**

If WebGL initialization fails, render a stable 2D fallback panel with stage, active actor, subtitle, event seq and sourceType. The event player must continue working without WebGL.

- [ ] **Step 6: Run build**

Run: `npm run build`.  
Expected: `/hearing-3d` is included in the production build with no server-component import of Three.js.

---

### Task 5: Build HUD, subtitles, materials and timeline

**Files:**
- Create: `components/hearing-3d/HearingHUD.tsx`
- Create: `components/hearing-3d/EventTimeline.tsx`
- Create: `components/hearing-3d/MaterialPanel.tsx`

**Interfaces:**

```tsx
<HearingHUD state={sceneState} mode="simple" | "professional" />
<EventTimeline store={playbackStore} onStateChange={setSceneState} />
<MaterialPanel state={sceneState} mode={viewMode} />
```

- [ ] **Step 1: Implement simple HUD**

Display current stage, issue label, active speaker, Chinese subtitle, play status and source badge (`人工脚本 Demo`/`后端运行`). Keep subtitle text selectable and readable at 1080p.

- [ ] **Step 2: Implement professional HUD**

Add event ID/seq, provenance, claim evidence status, review control, material IDs, `reasoning_meta.judgment_status`, citation verification and case warnings. A `failed/degraded/unverified` marker must be visually distinct and must not be rendered as a legal conclusion.

- [ ] **Step 3: Implement timeline controls**

Include play/pause, current seq, latest seq, jump to latest, gap display (“等待事件 N”), skipped range display and restart. When paused, incoming events buffer and do not animate the scene.

- [ ] **Step 4: Implement material panel**

Show only material references present in event payload. For missing/unauthorized material, display a non-clickable “材料不可用/权限不足”; never invent a URL or anchor.

- [ ] **Step 5: Add responsive fallback**

At narrow widths, keep speaker/subtitle/stage controls visible and collapse professional metadata into a panel. Do not hide the active speaker or subtitle.

---

### Task 6: Integrate the `/hearing-3d` experience page

**Files:**
- Create: `components/hearing-3d/Hearing3DExperience.tsx`
- Create: `app/hearing-3d/page.tsx`
- Modify: `components/navigation.tsx`
- Modify: `app/layout.tsx`
- Modify: `README.md`

**Interfaces:**

```tsx
export default function Hearing3DPage(): JSX.Element
```

- [ ] **Step 1: Build client orchestration**

`Hearing3DExperience` loads sample events, creates a PlaybackStore, runs a timer only when status is playing, applies one event per tick, and passes SceneState to 3D/HUD/timeline/material components. The page must be usable with JavaScript enabled and should show a clear loading/error state while the JSON is loading.

- [ ] **Step 2: Add source and mode controls**

Add “人工脚本 Demo” source label, simple/professional mode toggle, automatic/manual camera toggle and a reset button. Do not add real backend WebSocket/SSE in A phase; keep the adapter interface ready for B phase.

- [ ] **Step 3: Add navigation and metadata**

Add a navigation link named “仲裁听证 3D”. Set page metadata to identify it as a scripted placeholder demo, not a completed production 3D court.

- [ ] **Step 4: Document run instructions**

README must include `npm run dev`, `/hearing-3d`, current placeholder limitation, contract files, and the future formal asset replacement path.

- [ ] **Step 5: Manual smoke test**

Run dev server and verify: page loads, seven placeholders visible, event sequence advances, subtitle changes, camera controls work, pause buffers, jump-to-latest skips with visible notice, and professional metadata shows source/event IDs.

---

### Task 7: Tests, performance instrumentation and acceptance

**Files:**
- Modify: `components/hearing-3d/scene-reducer.test.ts`
- Modify: `components/hearing-3d/playback-store.test.ts`
- Create: `components/hearing-3d/cast-manifest.test.ts`
- Modify: `docs/superpowers/specs/2026-09-13-lexgentium-hearing-3d-design.md`
- Modify: `public/hearing-3d/README.md`

- [ ] **Step 1: Add manifest tests**

Assert exactly seven actor IDs, unique seat IDs, coordinates within room bounds, placeholder status explicit, and no formal model path is required for startup.

- [ ] **Step 2: Add event contract tests**

Assert all sample events have schema version, event ID, session/run ID, integer seq, type, timestamp, sourceType and payload; assert seq can be replayed without duplicate scene effects.

- [ ] **Step 3: Add reducer safety tests**

Cover unknown claim status, blocked/redacted utterance, missing material, missing translation, supersedes event, and unknown event type. Each case must preserve existing state and expose a visible warning rather than fabricate content.

- [ ] **Step 4: Add runtime performance instrumentation**

Sample FPS, frame time, DPR, renderer draw calls and WebGL fallback state once per second; expose values in professional mode and provide a copyable session summary for V16 evidence.

- [ ] **Step 5: Run complete verification**

Run:

```bash
npm run test:3d
npx tsc --noEmit
npm run build
```

Then perform the manual V01/V03/V04/V08/V09/V10/V11/V12/V13/V16 subset against the scripted demo. Record actual browser/device and results in the design spec; do not mark V02/V05/V06/V15 as passed without formal models/audio/export evidence.

- [ ] **Step 6: Commit**

Use a focused commit such as:

```bash
git add package.json package-lock.json app/hearing-3d components/hearing-3d public/hearing-3d app/layout.tsx components/navigation.tsx README.md docs/superpowers/specs/2026-09-13-lexgentium-hearing-3d-design.md
git commit -m "feat: add scripted 3D arbitration hearing MVP"
```

If the current workspace is still the tarball-based workspace without `.git`, hand this commit step to the git-owning agent after the verification commands pass.

---

## Phase A Completion Criteria

Phase A is complete only when all of the following are true:

1. `/hearing-3d` starts without formal 3D assets or an LLM/backend;
2. sample events play a 3–5 minute scripted hearing;
3. all seven seats are visible and correspond to the manifest;
4. four cameras work and manual mode is not automatically overridden;
5. every subtitle is traceable to eventId/seq;
6. pause/jump/duplicate/out-of-order/gap behavior is deterministic;
7. disconnect/fallback paths preserve received text and do not invent facts;
8. placeholder and scripted source status are visible;
9. a normal laptop browser reaches the 1080p/30 FPS target or displays the measured fallback/performance result;
10. `npm run test:3d`, `npx tsc --noEmit`, and `npm run build` pass.
