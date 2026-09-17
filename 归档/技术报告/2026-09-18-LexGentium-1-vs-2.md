# LexGentium-1 与 LexGentium-2 对照报告

- 对比时点：2026-09-18
- 对象：`D:\LexGentium-1`（现役工作树）与 `D:\LexGentium-2`（GitHub `main` 检出）
- 共同祖先：`1d91995`（`chore: 整理分层并收口观庭入口`，2026-09-15）
- 结论：两边已经不是「胶囊厅 vs 远端全套」。1 号库在 `integrate/lexgentium-2-useful` 上拣走了案例材料、新 Logo 和程序化坐姿人物。剩下的差在观庭壳、资产层和依赖钉法，不在推理引擎。

## 1. 两边身份

| 项 | LexGentium-1 | LexGentium-2 |
|---|---|---|
| 路径 | `D:\LexGentium-1` | `D:\LexGentium-2` |
| 分支 | `integrate/lexgentium-2-useful` | `main`（跟踪 `origin/main`） |
| HEAD | `2d5214f` 精选迁入程序化坐姿人物与庭室升级（2026-09-17 23:31 +0800） | `622af54` 前端: 换用新的品牌标志与站点图标（2026-09-17 16:07 +0800） |
| 祖先之后的提交 | 3 个（拣选） | 8 个（完整 PR 链 + 直推） |
| 工作区 | 干净 | 仅 `mock_court_system/next-env.d.ts` 换行 |
| 产品版本 | 0.8.0 | 0.8.0 |
| 本机前端 | `:3001`（这份库的 Next） | `:3000`（已在跑） |
| 本机后端 | 这份库的 FastAPI 未起 | `:8000`，`state.project_root` 指向 `D:\LexGentium-2\mock_court_system` |

远端仓库：`https://github.com/Hanyuan9766/LexGentium.git`。2 号库的 `main` 即该远端最新 tip。

## 2. 一句话

1 号库已经把 2 号库里「有用」的三块拣进来了：15 个已标案的原文与标注、新版法序智演标志、程序化坐姿人偶和庭室升级。2 号库多出来的是独立深色 Demo 页、sprite 立牌管线、`asset-adapter`、`three-vrm` 声明，以及把工作台壳拆掉。

不要整支把 2 的 `main` 合进 1：会盖掉工作台观庭壳和会话接线。

## 3. 提交关系

共同祖先 `1d91995` 之后：

**1 号库（拣选，3 个）**

1. `5dcc9d1` 法学材料: 入库 15 个已标案的原文与标注
2. `04d6d29` branding: 接入新版法序智演标志并保留现役导航
3. `2d5214f` hearing-3d: 精选迁入程序化坐姿人物与庭室升级

**2 号库（完整链，8 个）**

1. `9ebbad6` / `61eac29` PR #4：人物参考图立牌 + 异步纹理黑屏修复 + 桌椅升级
2. `b413bdb` / `059ae85` PR #5：真 3D 坐姿人偶 + 闪烁修复
3. `85a35fb` / `c78b040` PR #6：法序智演 Logo 替换前端品牌标示
4. `f7e6b9c` 法学材料: 入库 15 个已标案的原文与标注
5. `622af54` 前端: 换用新的品牌标志与站点图标

## 4. 已经对齐

### 4.1 法学材料

`法学材料/` 两边各 75 个文件，路径与内容一致（0 个独有、0 个内容差）。

包含：

- `案件1-9/`：9 个编号案原文
- `案例整理下载/`：案例 19–28 等原文
- `案例标注/`：15 份已填标注 xlsx；样本案例 1–6 另附原文与交付内容

边界（两边文件本身都写了，1 的 `AGENTS.md` / `SYSTEM_STATUS.md` 已跟上）：

- 本批只是原文本体与标注，没有做成 `research_packs`（无 `pack.json`、`documents/`、规则卡或原文锚点回填）
- 正式研究包计数仍为 **0**
- 15 份标注全部没有完成独立复核；案例 25 自注标注人为「待填（AI 辅助初标稿）」，不得当已复核数据使用

2 号库同名文档仍停在旧表述（「指南与候选母表 / 不是已标完的 10–20 案」），文件已经在，文档没改。

### 4.2 品牌资产

下列文件两边哈希相同：

- `mock_court_system/public/branding/lexgentium-logo.png`
- `mock_court_system/public/branding/lexgentium-logo-dark.png`
- `mock_court_system/public/icon-light-32x32.png`
- `mock_court_system/public/icon-dark-32x32.png`
- `mock_court_system/public/apple-icon.png`
- `mock_court_system/public/icon.svg`

1 号库导航已换成 Logo，但保留现役工作台顶栏，没有改成 2 的扁平导航。

### 4.3 庭上人物与房间

两边当前七席都走程序化坐姿人偶（`ProceduralCharacter`）：躯干/头/手臂/腿、按席配色、呼吸/点头/发言抬手，材质不透明。`ProceduralRoom` 桌椅、道具、灯光已升级。

`cast-manifest` 与播放器、事件适配、`scene-reducer` 测试文件两边字节相同。以当前清单看，七席画面等价。

### 4.4 引擎

对日常开发可视为同一套：

- `api_server.py` 一致
- `HearingRuntime` / `PleadRuntime` 一致
- `core/` 里 `llm_client.py`、`schemas.py` 只有换行差
- 民事 `dataset_1000` 与 RESEARCH（CISG / 纽约公约执行）分轨两边都在，没有把研究包装进民事训练集

## 5. 还不一样

### 5.1 观庭壳（主要产品差）

| 面 | 1 号库（现役） | 2 号库（GitHub main） |
|---|---|---|
| `/hearing-3d` 壳 | `WorkbenchShell` + 工作台顶栏 | 裸页，无工作台 |
| 页主题 | `bg-background`，跟整站 token | `min-h-screen bg-slate-950` 独立深色 Demo |
| 页首文案 | 「观庭 · Phase A / 程序化占位听证」 | 深色 Logo + 「仲裁听证 3D · 技术闭环 Demo」 |
| 会话接线 | `writeLastSessionId`；页脚按 session 显示 `sourceType` | 不写 last-session；页脚写死 `scripted_demo` |
| 人物路由 | `cast-manifest.asset_kind === "procedural"` | `asset-adapter.CHARACTER_ASSETS.mode` |
| 降级人物 | 25 行胶囊 + 球头 | 116 行 sprite 立牌（纹理、防黑屏、发言名牌） |
| 参考资产 | 只有 `public/hearing-3d/contracts/` | 另有 `reference/` 下 19 个文件 |
| `three` | `^0.186.0`，未声明 `three-vrm` | 钉 `0.180.0`，声明 `@pixiv/three-vrm@^3.5.5` |

### 5.2 1 号库刻意留下的 Phase A 壳

2 号库拆掉、1 号库还在的：

- `WorkbenchShell` 包着 `/hearing-3d`
- 双栏导航：营销条 + 工作台条（开庭 / 研究 / 观庭 / 复盘 / 系统）
- `ThemeProvider`、Geist、`data-scheme="ink"`、跳到正文
- `CommandPalette`、会话芯片、`/api/health` 绿点、配色切换、登录/开通
- `navigation.tsx`：1 约 383 行，2 约 120 行扁平链
- `app/layout.tsx` 标题：1 为「法序智演 LexGentium｜国际商事仲裁听证仿真」；2 为「法序智演 LexGentium \| 基于扩展式博弈建模的多智能体协同模拟法庭系统」，并带 `generator: "v0.app"`

### 5.3 2 号库还独有、1 没拣的

| 项 | 要不要拣 | 说明 |
|---|---|---|
| `asset-adapter.ts` | 看下一步是否接 VRM / 立牌 | `procedural / vrm / glb / sprite` 四级。现在七席都是 procedural，不接也能跑。 |
| sprite 版 `PlaceholderCharacter` + `reference/` | 仅当要切回立牌或做对照 | 约 9 张 web 人像 + 全景 + P0 SVG/`roles.json`/`build.py`。正式模型到位后这条会闲置。 |
| 独立深色 Demo 页 + 扁平导航 | 不要整支覆盖 | 会拆掉 ThemeProvider、Geist、CommandPalette、SessionChip、HealthDot。 |
| layout 标题与 `v0.app` | 不必 | 产品文案应以 1 的工作台表述为准。 |
| `three` 钉 0.180 + `three-vrm` | 要接 VRM 再钉 | 1 的 `package-lock.json` 里有残留 `^3.5.5`，`package.json` 没声明。 |

### 5.4 hearing-3d 文件清单

`mock_court_system/components/hearing-3d/`：1 有 19 个文件，2 有 20 个。

- 2 独有：`asset-adapter.ts`
- 内容仍不一致（7）：`CastLayer.tsx`、`Hearing3DExperience.tsx`、`Hearing3DScene.tsx`、`HearingHUD.tsx`、`PlaceholderCharacter.tsx`、`ProceduralCharacter.tsx`、`ProceduralRoom.tsx`
- 字节相同（12）：`backend-event-adapter.ts` 及测试、`CameraDirector.tsx`、`cast-manifest.ts` 及测试、`contracts.ts`、`EventTimeline.tsx`、`MaterialPanel.tsx`、`playback-store.ts` 及测试、`scene-reducer.ts` 及测试

`app/` 路由树两边都是 108 个文件；内容只差 `app/layout.tsx` 和 `app/hearing-3d/page.tsx`。

`public/hearing-3d/`：1 有 5 个（README + 4 份 contracts）；2 另加 `reference/` 19 个。两边 README 文案不同。

## 6. 本机运行注意

对照当时的实际端口：

- `:3000` 和 `:8000` 属于 **LexGentium-2**，不是 1 号库
- 1 号库前端若 3000 被占，会落到 **`:3001`**
- 在 1 号库里开真听证，必须起这份目录自己的 `python api_server.py`，并填这份 `.env` 的 `LLM_API_KEY`；不要去打 2 的 `:8000`

观庭无 session 时播样例（`sourceType: scripted_demo`），不依赖后端。开庭页 `/conversation` 的「新建」在未选研究包时是灰的——正式研究包仍为 0，这是数据边界，不是对比引入的回归。

## 7. 建议

1. **维持 1 为现役产品树。** 工作台 + 新 Logo + 坐姿人偶 + 案例材料已经齐。
2. **不要整支合并 2 的 `main`。** 会盖掉工作台观庭壳和 `writeLastSessionId` / 动态 `sourceType`。
3. **需要立牌或 VRM 时再搬 `asset-adapter` 和 `reference/`。** 现在七席都走 procedural，搬了也不改变当前画面。
4. **开庭不要打 `:8000`。** 那个后端属于 2。

## 8. 方法

- 两边 `git rev-parse` / `git log` / `git status`
- 共同祖先 `1d91995` 之后的提交列表
- `mock_court_system/components/hearing-3d/`、`app/layout.tsx`、`app/hearing-3d/page.tsx`、`navigation.tsx`、`package.json`、`public/branding/`、`法学材料/` 的文件清单与内容对照
- 1 号库相对 `1d91995` 的 `git diff --stat`（85 files，+419 / −63，另含案例二进制入库）
- 本机端口探测：`:8000/health` 返回的 `state.project_root` 指向 LexGentium-2

本报告只记录对照当时的树，不代替 `SYSTEM_STATUS.md`。权威产品现状仍以 `mock_court_system/docs/SYSTEM_STATUS.md` 为准。
