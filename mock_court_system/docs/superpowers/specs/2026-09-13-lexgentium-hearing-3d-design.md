# LexGentium 仲裁听证 3D 系统设计规范

> 日期：2026-09-13  
> 范围：首版仲裁听证 3D 观看、回放与演示闭环  
> 资产策略：正式 VRM/GLB 尚未交付，第一期使用明确标注的程序化占位资产；正式资产只替换资产适配层

## 1. 目标与非目标

### 目标

构建 LexGentium 的 `/hearing-3d` 页面，支持：

- 10m × 8m 仲裁室的程序化 3D 场景；
- 交付包定义的 7 个角色与 7 个席位；
- 全景、首席中景、申请方中景、被申请方中景四个机位；
- 自动导播与手动镜头切换；
- 中文字幕、阶段、争点、当前发言人和来源标记；
- `sample-events.jsonl` 人工脚本播放；
- 播放、暂停、跳转到最新、事件去重、乱序缓冲和断线后继续已接收内容；
- 材料摘要面板与事件来源/版本/锚点展示；
- 占位资产、人工脚本、降级事件明确显示来源，不伪装成正式模型或真实裁决。

### 非目标

第一期不承诺：

- 正式人物 VRM/GLB 外观；
- 动作捕捉、正式口型和正式配音；
- 视频导出生产质量；
- 真实后端实时推理接入；
- 生产级 WebSocket 集群；
- 法律结论的自动生成或法律效力。

## 2. 设计依据

采用交付包 v1.1 的规范：

- `contracts/cast-manifest.json`：7 个 actor_id 与资产状态；
- `contracts/event-contract.json`：事件类型、来源、顺序、修订关系；
- `contracts/scene-layout.json`：房间、坐席、桌面、证据屏和相机坐标；
- `contracts/sample-events.jsonl`：人工脚本事件样例；
- `acceptance/checklist.csv`：18 项验收要求。

交付包声明 `runtime_assets_included: false`，因此所有正式资产路径均为可选，运行时必须有 placeholder 降级。

## 3. 系统架构

```text
app/hearing-3d/page.tsx
  └── Hearing3DExperience（客户端边界）
       ├── Hearing3DScene（Canvas / renderer）
       │    ├── ProceduralRoom
       │    ├── CastLayer
       │    ├── CameraDirector
       │    └── EvidenceScreen
       ├── HearingHUD
       ├── EventTimeline
       ├── MaterialPanel
       └── PlaybackController

sample-events.jsonl / backend adapter
  → EventNormalizer
  → PlaybackStore（按 seq 排序、去重、游标、断线补取）
  → SceneReducer（纯状态更新）
  → 3D/HUD 渲染
```

### 边界原则

- 3D 组件不直接读取 CIAgent、StateMachine 或后端内部对象；
- 所有后端/脚本输入先转换为统一 `HearingEvent`；
- `SceneReducer` 是纯函数，可脱离 WebGL 单测；
- 资产加载失败不能阻塞事件播放，必须降级到 placeholder 或文字；
- 3D 渲染层只消费 `SceneState`，不负责业务推理。

## 4. 数据模型

### 4.1 CastManifest

```ts
export type AssetStatus = "formal" | "placeholder" | "reference"

export interface CastMember {
  actorId: string
  label: string
  name: string
  status: AssetStatus
  modelUrl?: string
  referenceUrl?: string
  seatId: string
  seatToRoot: [number, number, number]
  forwardAxis: [number, number, number]
  scale: number
}
```

首期固定 7 个 actor_id：`judge`、`clerk`、`plaintiff_counsel`、`plaintiff_party`、`defendant_counsel`、`defendant_party`、`interpreter`。

### 4.2 HearingEvent

```ts
export type HearingEventType =
  | "session_started"
  | "stage_changed"
  | "issue_opened"
  | "utterance_committed"
  | "claim_status_changed"
  | "playback_policy_changed"
  | "session_finished"

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
```

事件处理规则：

- `seq` 是会话内唯一播放顺序，不能以到达顺序替代；
- 已消费的 `eventId` 去重；
- 乱序事件进入缓冲区，等待缺失 seq 或超时；
- supersedes 只更新视图状态，保留被修订事件以便审计；
- sourceType、provenance 始终显示在调试/专业模式。

### 4.3 SceneState

```ts
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
```

## 5. 3D 场景设计

### 5.1 坐标与布局

- 单位：米；x 向右、y 向上、z 朝向首席仲裁员；
- 房间：x[-5,5]、z[-4,4]、height 3.2；
- seat reference 使用 chair seat center，不直接假设角色 root；
- 首期程序化房间：地面、墙、三张桌、秘书桌、七张椅、证据屏；
- 正式模型替换时由 `seatToRoot/forwardAxis/scale` 校准，不改业务坐标。

### 5.2 资产降级

- formal：正式 VRM/GLB 成功加载；
- placeholder：当前程序化角色，必须在 HUD/调试模式显示“占位资产”；
- reference：只有参考 PNG，不能加载进场景，显示“仅参考图”。

### 5.3 相机

四个交付机位：

- wide：全景；
- presiding_medium：首席中景；
- claimant_medium：申请方中景；
- respondent_medium：被申请方中景。

自动导播规则：

- utterance_committed：切到 activeActor 所属中景；
- issue_opened/stage_changed：短暂切 wide 或 presiding_medium；
- 手动切镜头后锁定，直到用户恢复自动；
- 不自动抢回用户手动相机。

## 6. 播放与事件状态机

### 6.1 PlaybackStore

职责：事件导入、去重、乱序缓冲、游标、暂停、跳转、断线恢复。

核心 API：

```ts
append(events: HearingEvent[]): void
pause(): void
resume(): void
jumpTo(seq: number): void
jumpToLatest(): void
consumeNext(): HearingEvent | null
getCursor(): number
getPendingGap(): number[]
```

### 6.2 SceneReducer

每个事件类型只产生确定性的 SceneState 变化：

- session_started：初始化会话、角色、材料目录；
- stage_changed：阶段更新，导播切换；
- issue_opened：争点 HUD 更新；
- utterance_committed：字幕、activeActor、talk/idle 动作；
- claim_status_changed：事实/证据状态更新；
- playback_policy_changed：目标事件 allow/blocked/redacted；
- session_finished：状态 finished，不把 outcome 自动显示为法律裁决。

### 6.3 断线策略

- 已收到事件继续播放；
- 新事件从 `lastSeq + 1` 补取；
- 重复事件按 eventId 去重；
- 缺口显示“等待事件 N”，不自行补造字幕、事实或动作；
- 语音失败保留文字；模型资源失败保留 HUD/材料/字幕。

## 7. HUD 与观看模式

### 简明模式

显示：阶段、当前发言人、字幕、争点标题、播放状态。

### 专业模式

额外显示：

- eventId/seq/sourceType；
- claim evidence_status/review_control；
- material_id/version/anchor；
- reasoning_meta（judgment_status/citation_report/case_warnings）；
- 未知事实、未验证法条和降级标识。

两种模式必须消费同一 SceneState，不允许各自推理事实。

## 8. 与 LexGentium 后端接入

第一期只接脚本事件；第二期增加 adapter：

```text
Conversation/Game/Case API
  → BackendEventAdapter
  → HearingEvent
  → PlaybackStore
```

adapter 负责：

- 把 CD/DD/CI 消息映射为 utterance_committed；
- 把 StageMachine 状态映射为 stage_changed；
- 把 FactLedger/IssueGraph/IRAC/ReasoningMeta 映射为 issue、claim、material 事件；
- 继承 sourceType、model、promptVersion、retrievalIds、degraded 状态；
- 不把缺失字段推断成已确认事实。

## 9. 性能设计

目标：普通无独显笔记本、1080p、30 FPS。

首期约束：

- placeholder 角色低面数、共享几何与材质；
- 限制实时阴影与后处理；
- 角色不发言时不更新复杂动画；
- 事件播放与渲染解耦；
- 每 1 秒采样 FPS、frame time、draw calls、内存；
- 设备能力不足时自动关闭阴影、降低 DPR、保留 HUD 和字幕。

验收证据：至少 5 分钟场景运行日志，记录硬件、浏览器、DPR、平均/最低 FPS、卡顿帧数。

## 10. 测试设计

### 单元测试

- CastManifest 七席完整性；
- scene-layout 坐标读取；
- event schema 解析；
- seq 乱序排序、eventId 去重、supersedes；
- SceneReducer 每种事件类型；
- playback pause/jump/disconnected；
- unknown/frozen/blocked/redacted 不越权；
- asset formal→placeholder 降级。

### 集成测试

- sample-events.jsonl 完整播放；
- 刷新后 cursor 恢复；
- 断线后补取无重复；
- Next.js `/hearing-3d` 页面 build；
- 后端事件 adapter 输出符合 1.1 协议。

### 人工验收

对应交付包 V01-V18：空间、人物、镜头、事件一致性、声画同步、语言切换、材料关联、未知事实、五态、暂停跳转、断线刷新、故障降级、两类 Demo、交互封装、视频导出、性能、权限版本、端到端闭环。

## 11. 分期交付

### A 期：完整技术闭环

- `/hearing-3d` 页面；
- 程序化房间 + 七个占位角色；
- 四机位；
- event types / PlaybackStore / SceneReducer；
- sample-events.jsonl 播放；
- HUD、字幕、时间线、暂停、跳转、断线缓冲；
- 占位/脚本来源标识。

### B 期：后端事件接入

- 后端 adapter；
- FactLedger/IssueGraph/IRAC/ReasoningMeta 映射；
- SSE 或 WebSocket 实时事件；
- 重连补取；
- 材料摘要与权限控制。

### C 期：正式资产与表演层

- 房间 GLB；
- 七个角色 VRM/GLB；
- seat_to_root/forwardAxis/scale 校准；
- idle/listen/talk/nod；
- 口型、中文音频、英文切换；
- 视频导出与 V01-V18 完整验收。

## 12. 第一阶段验收状态

已完成的技术门禁：

- `/hearing-3d` 页面已接入现有 Next.js；
- 程序化房间、7 个 placeholder 角色、4 个机位已实现；
- sample events 加载、事件 reducer、播放 store、字幕 HUD、时间线和材料状态已实现；
- 3D 纯逻辑测试 8/8 通过；
- `npx tsc --noEmit` 通过；
- `npm run build` 通过；
- 浏览器冒烟确认页面标题、占位资产声明、7 席、9 条 scripted demo 事件、机位和播放控制均可见；
- 正式 VRM/GLB、动作、语音、视频导出和真实后端事件仍未验收。

## Phase B 当前实现状态

已加入轻量后端事件适配器：

- `backend-event-adapter.ts` 把现有 conversation payload 转成 HearingEvent 1.1；
- `/hearing-3d?sessionId=<id>` 读取现有 LexGentium conversation API；
- 后端事件 sourceType 标记为 `backend_run`，脚本事件仍标记为 `scripted_demo`；
- 会话完成只映射为 session_finished，不自动宣称为法律裁决；
- 适配器有 2 个单元测试。

当前仍未接入后端实时 SSE/WebSocket；会话预览读取已有会话快照，适合第一版联调。

Phase B 后续补充：实时 conversation SSE 已接入页面级发送；reasoning_meta、claims、material_refs 进入 SceneState/HUD/材料面板；自动导播依据 active actor 选择机位，手动模式不会抢回；PlaybackStore 支持自动逐段播放、缺口 seq、断线状态和已接收内容保留。

## 13. 第一阶段验收标准

A 期完成必须满足：

1. 无正式模型、无后端、无 LLM 也能启动；
2. sample-events.jsonl 能完整播放一个 3-5 分钟 Demo；
3. 七席可见，四机位可切换；
4. 手动镜头不会被自动导播抢回；
5. 每条字幕能回指 eventId/seq；
6. 断线后不丢已接收内容、不重复消费；
7. 未知事实不自动补造；
8. 占位资产、人工脚本来源显式显示；
9. 普通笔记本 1080p 目标 30 FPS；
10. `npm run build`、单元测试和脚本事件回放全部通过。
