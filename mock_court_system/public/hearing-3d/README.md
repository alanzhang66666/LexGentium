# 仲裁听证 3D 第一阶段资产与事件说明

当前页面是 LexGentium 的第一阶段技术闭环 Demo：

- 房间和角色使用程序化 placeholder，不是正式 VRM/GLB；
- 事件来源是 `scripted_demo`，来自交付包中的结构样例，不是真实案件运行；
- 当前不提供正式动作捕捉、口型、配音、视频导出或后端实时事件；
- 正式资产到位后，替换 cast manifest 的 `modelUrl`、`seatToRoot`、`forwardAxis` 和 `scale`，不改事件播放器和业务状态层。

合同文件：

- `contracts/scene-layout.json`：房间、桌面、座席与相机坐标；
- `contracts/cast-manifest.json`：七个 actor_id 与参考映射；
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

## 角色立牌（sprite 模式）

当前七席使用 P0 交付包的人物参考图作为 billboard 立牌：

- 立牌贴图取自 `reference/char-*-web.jpg`（原图压缩版，单张约 40KB）；
- 映射关系集中在 `components/hearing-3d/asset-adapter.ts`：judge=char-9、clerk=char-6、plaintiff=char-1、defendant_counsel=char-4、defendant_party=char-3、interpreter=char-5；
- 加载失败会自动降级为胶囊体，不会出现隐形角色；
- 正式 VRM/GLB 到位后，在 asset-adapter 中把 `mode` 改为 `vrm`/`glb` 并填 `model_url`，场景代码无需改动；
- `reference/` 内的 SVG（平面/立面/剖面/HUD/色票/双语名牌）与 `roles.json`、`p0-design-spec.html` 来自 P0 设计交付包；原始大尺寸 PNG 未入库（每张 1.5-2MB），仅保留本地。

已知渲染注意点：R3F v9 对已挂载材质后设置 `map` 不会触发 shader 重编译，异步加载的纹理必须通过 `key={texture.uuid}` 强制重挂材质，否则显示为黑色（PlaceholderCharacter 已处理，纹理加载失败自动回退胶囊体）。
