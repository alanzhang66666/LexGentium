# 仲裁听证 3D 第一阶段资产与事件说明

当前页面是 LexGentium 的第一阶段技术闭环 Demo：

- 房间仍使用程序化环境；9 个新增角色使用供应商 OBJ + PBR 运行资产，司法警察继续使用独立 OBJ；
- 事件来源是 `scripted_demo`，来自交付包中的结构样例，不是真实案件运行；
- 当前不提供正式动作捕捉、口型、配音、视频导出或后端实时事件；
- 正式资产到位后，替换 cast manifest 的 `modelUrl`、`seatToRoot`、`forwardAxis` 和 `scale`，不改事件播放器和业务状态层。

合同文件：

- `contracts/scene-layout.json`：房间、桌面、座席与相机坐标；
- `contracts/cast-manifest.json`：9 个 actor_id、角色映射与运行资产路径；
- `contracts/event-contract.json`：HearingEvent 1.1 草案；
- `contracts/sample-events.jsonl`：人工结构样例。

访问路径：`/hearing-3d`。页面支持简明/专业模式、四个机位、逐事件播放、暂停、继续、跳到最新和来源标记。

后端会话预览：`/hearing-3d?sessionId=<LexGentium conversation session id>`。页面会通过现有 `/api/conversation/{sessionId}` 读取会话，并由 `backend-event-adapter.ts` 转换成 `backend_run` 事件；未提供 sessionId 时使用 `scripted_demo` 样例。

当提供 sessionId 时，页面还会显示实时输入框：消息通过现有 `/api/conversation/{sessionId}/message/stream` SSE 发送，增量文本即时显示，最终回复转换为新的 `utterance_committed` HearingEvent 驱动 3D 字幕和角色状态。当前仍是页面级 SSE 联调，不是 WebSocket 集群。

## 推理状态与自动导播

- 专业模式会显示 `judgment_status`、法条回查 checked/verified/unverified、案件契约告警；
- claims、material_refs、reasoning_meta 会通过 SceneReducer 进入右侧材料面板和 HUD；
- 自动导播根据 active actor 选择申请方、被申请方、首席中景；切换为手动镜头后不会自动抢回；
- 真实会话里的 reasoning_meta 会随实时 utterance 事件更新；没有元数据时不会伪造状态。
- 时间线支持自动逐事件播放、暂停、继续、跳到最新；
- 缺失 seq 会显示等待事件编号，连接中断保留已接收内容并展示断线状态；
- `pending_gap` 与 `skipped_seqs` 会进入专业模式和时间线提示。

## OBJ 角色资产

`models/judicial-police/` 保存供应商交付的浏览器运行用轻量化 OBJ、MTL 和四张 PBR 贴图。`JudicialPoliceModel.tsx` 使用 Three.js `OBJLoader` 读取轻量化网格，并显式绑定 base color、metallic、roughness、normal 贴图；`/hearing-3d` 会将其作为独立的司法警察角色显示在入口前侧。运行用 OBJ 保留 UV 和材质并降到约 18 万顶点、37 万三角面，避免浏览器加载超大原始文件。

`models/roles/` 保存本次新增的 9 个角色运行资产：审判长、书记员、中方代理律师、外方代理律师、外方企业代表、外籍被告人、法庭口译员、公诉人、外籍事实证人。每个角色目录包含降面后的 `model-optimized.obj`、`material.mtl` 和四张 PBR 贴图；`ObjCharacterModel.tsx` 显式绑定 PBR 贴图并按席位校准根节点。8 个高模原始 OBJ 约 75 万顶点、150 万三角面，运行版使用 `scripts/optimize-obj.mjs` 保留 UV、聚合位置顶点并减少退化面，避免九个高模同时解析时阻塞首屏。

角色模型按席位逐个进入渲染树；等待后续模型解析时先显示程序化 3D 回退，因此页面不会因为某个大 OBJ 尚未完成解析而出现空 Canvas。

## 角色渲染回退（procedural 3D 人偶）

OBJ 加载失败或仍在等待时使用程序化 3D 坐姿人偶（`ProceduralCharacter.tsx`）：真 3D 几何体（躯干/头/手臂/腿部），按席位配色，带呼吸、点头、发言抬手动画；材质全部不透明，避免透明排序闪烁。

- `asset-adapter.ts` 统一管理四种模式：`procedural`（默认）/ `vrm` / `glb` / `sprite`；
- `sprite` 模式保留 P0 交付包人像 billboard（`reference/char-*-web.jpg`，~40KB/张），映射关系同样在 asset-adapter；
- 纹理加载失败自动降级胶囊体，不会出现隐形角色；
- 正式 VRM/GLB 到位后，把 `mode` 改为 `vrm`/`glb` 并填 `model_url`，场景代码无需改动；
- `reference/` 内的 SVG（平面/立面/剖面/HUD/色票/双语名牌）与 `roles.json`、`p0-design-spec.html` 来自 P0 设计交付包；原始大尺寸 PNG 未入库（每张 1.5-2MB），仅保留本地。

已知渲染注意点：R3F v9 对已挂载材质后设置 `map` 不会触发 shader 重编译，异步加载的纹理必须通过 `key={texture.uuid}` 强制重挂材质，否则显示为黑色（PlaceholderCharacter 已处理）。透明材质参与排序是画面闪烁的常见来源——立牌/台座均已改为不透明材质。Next.js dev 对 `public/` 是启动时快照，新增/改名静态文件后必须重启 dev server。
