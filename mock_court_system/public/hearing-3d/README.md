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
