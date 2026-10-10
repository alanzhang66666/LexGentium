# JoyCode 部署与校赛验收

**当前状态：最小可部署演示工程，非原平台完整运行时。**

## 平台设置

1. GitHub 分支：`competition/joycode-school`；工作目录：`人工智能校赛/`。
2. 运行环境：Node.js 20+，启动命令：`npm start`。
3. 监听：`0.0.0.0:8080`，无需数据库、对象存储或多容器。
4. 配置公共健康探针：`GET /api/health`，要求 mode 为 `synthetic_replay`。
5. `npm test` 后手动验证五个页面及临时 session。容器重启后 session 将丢失。

## 当前内容与正式规划

- 当前已实现：合成黄金案例读取、事实台账、争议焦点、未复核规则说明、预置 CD/DD 摘要、听证事件回放、四维状态复盘。
- 尚未实现：真实 LLM Agent、Python Hearing/Plead Runtime、三维 Three.js 场景、正式 Research Pack、持久化、多用户鉴权、真实策略量表。
- 不应使用“实时多智能体仲裁”“正式法律意见”“已完成 Research Pack”描述当前部署。
- 如果平台规定必须使用 Dockerfile，可在经平台验证后增加单阶段 Node 镜像文件；当前工程不需要 Compose。

## 验收口径

最终校赛必须补：黄金案来源及独立复核、带真实 3D 画面的同案回放、最少三个可复现 Prompt 及真实输出、匿名性、浏览器 E2E 和实际 JoyCode 部署日志。PPT 数值全部来自最终候选版本实测。
