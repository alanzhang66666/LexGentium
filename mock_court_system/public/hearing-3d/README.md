# 仲裁听证 3D 资产与事件说明

`/hearing-3d` 是 LexGentium 的国际商事仲裁观庭入口。房间使用程序化环境，13 个角色使用 OBJ 与 PBR 运行资产；正式动作捕捉、口型、配音和视频导出尚未接入。

## 角色资料来源

角色元数据来自：

- `3D建模方案/角色资料/`：13 套原始 OBJ、MTL 与 PBR 贴图；
- `3D建模方案/说明/涉外模拟法庭人物性转版生成档案.md`：姓名、身份、外观和连续性标记。

设计目录不是运行入口，也不会直接复制到 `public/`。浏览器使用 `public/hearing-3d/models/` 下既有的 Web 优化派生资产，`asset-adapter.ts` 负责一对一映射。

当前国际商事仲裁角色为：

1. 首席仲裁员 周屹；
2. 仲裁员 陈启澜；
3. 仲裁员 何敬；
4. 仲裁庭秘书 林澄；
5. 申请人首席代理律师 顾清衡；
6. 申请人共同代理律师 谢衡宁；
7. 申请人代表 陆玮宁；
8. 被申请人代理律师 沈嘉宁；
9. 被申请人代表 Marco Rossi；
10. 听证口译员 唐闻；
11. 专家证人 Dr. Leila Haddad；
12. 事实证人 Adrian Tan；
13. 会务安保 赵峥。

原“公诉人”资产仅复用为申请人共同代理律师；原“司法警察”资产仅承担会务安保职能。无最新角色资料目录对应且不适用于仲裁的 `foreign-defendant` 不再进入运行 cast。

这些姓名属于产品人物档案，不代表接入会话中的真实参与人。实际案件身份、陈述与材料始终以会话数据为准。

## 页面数据行为

无 `sessionId` 时，页面显示等待接入状态，不自动载入合成事件。后端会话入口为：

`/hearing-3d?sessionId=<LexGentium conversation session id>`

页面通过 `/api/conversation/{sessionId}` 读取会话，由 `backend-event-adapter.ts` 转换为 HearingEvent 1.1；实时输入通过现有 SSE 接口发送，最终回复驱动字幕、人物状态和自动镜头。

内部的 `contracts/sample-events.jsonl` 仅作为事件协议回放夹具保留，不由产品页面默认加载。

## 运行合同

- `contracts/scene-layout.json`：房间、桌面、座席与相机坐标；
- `contracts/cast-manifest.json`：13 个角色、设计来源与运行资产路径；
- `contracts/event-contract.json`：HearingEvent 1.1 合同；
- `contracts/sample-events.jsonl`：协议回放夹具。

旧 `actor_id` 在必要处继续作为事件和资产兼容键；用户界面只显示新的仲裁角色称谓与人物姓名。

## 角色加载与回退

角色模型按席位逐个进入渲染树。运行 OBJ 由 `scripts/optimize-obj.mjs` 从角色资料重建：头部用更细的网格、身体保持紧凑，并丢掉未引用 UV。OBJ 等待或加载失败时使用程序化 3D 人偶，保留席位、朝向、呼吸、点头和发言动作。正式 VRM/GLB 到位后，可通过 `asset-adapter.ts` 切换模型模式而不改变事件播放器。

材料不可用或权限不足时，观庭页面不会生成下载地址。Next.js 开发服务对静态资源有缓存；新增或改名运行资产后需要重启前端服务。
