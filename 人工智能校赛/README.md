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

当前是 **校赛可部署的最小骨架**：`/global-dispute` → `/research` → `/conversation` → `/hearing-3d` → `/evaluation`，统一 synthetic demo 案件与临时 session。听证为**预置事件回放，不是实时 Python HearingRuntime**；CD/DD 为事实与争议的结构化演示，不是在线 LLM 推理；3D 入口当前是二维听证舞台占位，**不是 Three.js 3D 渲染**。不将其作为真实模型推演或正式法律意见。后续才移植原平台 Three.js 场景，并引入受约束的实时 LLM 适配层。

## 接口

- `GET /api/health`：健康检查及模式
- `GET /api/case`：黄金案例与研究资料
- `POST /api/session`：生成内存会话 ID；容器重启后失效
- `GET /api/session/:id`：获取本容器生成的会话摘要

部署验证：`npm test`、`curl -f http://localhost:8080/api/health` 和人工走通五个页面。服务不接受案件文件上传，不储存用户敏感材料。非生产、多租户或法律服务系统。

## 后续开发顺序

1. 从现有 `mock_court_system` 抽取稳定 API/事件协议以及 Three.js 场景，替换二维占位；不要复制 Python 运行时。
2. 对黄金案完成合成数据审查、法律规则锚点和独立复核，形成合格 Research Pack 前不可宣称正式包。
3. 建立 Node LLM adapter（仅服务端环境变量），提供真实模式与回放模式标记；补齐 CD/DD/CI 与策略评测的后端执行能力。
4. 补充访问鉴权、请求体限制、容器重启行为、浏览器 E2E、匿名化及发布证据，再制作 PPT/视频。
5. 不能把 DevCloud 此版本的回放页面宣传成原平台完整多智能体执行链。
