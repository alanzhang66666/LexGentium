# 法序智演 LexGentium · 人工智能校赛版

独立的 **JoyCode / JD DevCloud 单容器运行工程**。比赛主题固定为 **通用赛道 · 出海**，保留“法序智演 LexGentium”品牌。主工程仍在 `../mock_court_system/`，本目录不覆盖其 FastAPI/Python 代码。

## 运行与部署

要求 Node.js 20+。不依赖 Docker Compose、PostgreSQL、MinIO、Redis、MySQL，也不使用 Python 进程。

```bash
cd 人工智能校赛
npm start
# http://localhost:8080
npm test
```

JoyCode 项目根目录选择 `人工智能校赛/`；启动命令 `npm start`，监听 `0.0.0.0:8080`。无需 `npm install` 下载依赖（仅 Node 标准库）。如平台不支持中文作为构建根目录，使用构建上下文复制本目录内容至容器工作目录，但仓库路径保持不变。

## 运行模式及真实性边界

当前是 **校赛可部署的最小骨架**：`/global-dispute` → `/research` → `/conversation` → `/hearing-3d` → `/evaluation`，统一 synthetic demo 案件与临时 session。听证为**预置事件回放，不是实时 Python HearingRuntime**；CD/DD 为事实与争议的结构化演示，不是在线 LLM 推理；观庭现为 **SVG/CSS 2.5D 仲裁庭**，支持座席高亮与事件回放，**不是 Three.js 3D 渲染**。不将其作为真实模型推演或正式法律意见。后续才移植原平台 Three.js 场景，并引入受约束的实时 LLM 适配层。

## 接口

- `GET /api/health`：健康检查及模式
- `GET /api/case`：黄金案例与研究资料
- `POST /api/session`：生成内存会话 ID；容器重启后失效
- `GET /api/session/:id`：获取本容器生成的会话摘要

部署验证：`npm test`、`curl -f http://localhost:8080/api/health` 和人工走通五个页面。服务不接受案件文件上传，不储存用户敏感材料。非生产、多租户或法律服务系统。

## 后续开发顺序

1. 沿用现有会话 ID 和 HearingEvent 语义，维护 SVG/CSS 2.5D 观庭；校赛阶段不再把完整 Three.js 场景移植作为 P0。
2. 对黄金案完成合成数据审查、法律规则锚点和独立复核，形成合格 Research Pack 前不可宣称正式包。
3. 建立 Node LLM adapter（仅服务端环境变量），提供真实模式与回放模式标记；补齐 CD/DD/CI 与策略评测的后端执行能力。
4. 补充访问鉴权、请求体限制、容器重启行为、浏览器 E2E、匿名化及发布证据，再制作 PPT/视频。
5. 不能把 DevCloud 此版本的回放页面宣传成原平台完整多智能体执行链。

## 2026-10-11 开发增量

- 已增加 `engine/legal.js`：合成案件结构校验、事实状态与来源、未知事实清单、法律人工复核要求。
- 已增加 `engine/llm.js`：可选 OpenAI-compatible `/chat/completions` 端点，缺少服务端密钥、调用失败或超时即返回明确标记的 `structured_demo`；只有真实调用成功才标记 `live_llm`。模型草稿未经法学独立复核。
- 已增加 `POST /api/analyze`：校验 session 和提问长度，限制 8 KiB 请求体；不接收用户上传原始法律材料。
- 已增加 Node `Dockerfile`、GitHub Actions 独立工作流、Node 合同测试。
- `legal/法律定位与数据边界.md` 明确出海企业法务及律师为主要使用者，并规范仲裁术语和合成数据使用边界。

**仍未完成正式发布验收**：原平台完整 Three.js 三维场景（校赛不作为 P0）、完整 CD/DD/CI 多智能体在线运行、来源原文与规则条款独立复核、合规持久化与真实身份管理、JoyCode 实际环境测试。对外展示时必须明确该版本为独立轻量校赛适配，不代表原平台所有功能已移植。

## 2026-10-11 进一步开发：策略与会话合同

- `engine/journey.js` 为同一黄金案生成 `synthetic_replay` 听证事件、定性策略比较与 `demo_status` 复盘合同。
- `GET /api/hearing?session_id=...`、`GET /api/strategy?session_id=...`、`GET /api/review?session_id=...` 校验临时会话身份；无效或过期的会话返回 404。
- 新增 `/strategy` 页面，提供补证、谈判、仲裁准备三种定性路径，相关事实由 F1/F2/F3 标识；**不提供模拟出来的胜诉率、收益评分**。
- 已添加 `tests/journey.test.js` 的接口与数据合同回归检查；实际 GitHub Actions 和 JoyCode 环境测试结果仍需确认。
- 当前 Web 听证页面仍在使用合成事件的前端顺序回放，服务端接口已提供同源会话身份，**并非已完成的实时 3D 或多智能体听证**。

## 2.5D 观庭（方案 B，2026-10-11）

- `/hearing-3d` 路由保留历史兼容，但页面呈现和标题已改为 **仲裁开庭可视化 · 2.5D**。
- `public/hearing-ui.js` 使用 SVG 绘制仲裁庭透视地面和三个角色席位，当前发言席位金色高亮。
- 从 `GET /api/hearing?session_id=...` 加载当前会话的合成事件；支持上一条、下一条、自动播放、暂停与时间线跳转。
- 仅对可识别的模拟角色显示座席，保留 `synthetic_replay` 标识。播放不调用 Python HearingRuntime，也不暗示运行了真实多智能体听证。
- `tests/hearing-ui.test.js` 检查浏览器模块可访问、页面载入与同一会话的事件协议；视觉及键盘操作仍需浏览器 E2E 验证。
