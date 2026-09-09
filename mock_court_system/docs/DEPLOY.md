# LexGentium 部署指南

部署目录是 **`mock_court_system/`**。Web 主路径：`api_server.py`（FastAPI）+ Next.js。`main.py` 只用于离线批跑，不要当生产入口。

## 1. 服务器准备

- 操作系统：Ubuntu 20.04 / 22.04 或同等环境
- 建议：2 核 2–4GB；开放后端端口（默认 TCP 8000）与前端端口（默认 3000，或由 Nginx 反代）
- Python 3.9+、Node.js 20+

```bash
sudo apt update
sudo apt install python3-pip python3-venv git -y
# Node 20+ 按发行版另行安装
```

## 2. 部署代码

将 `mock_court_system` 放到服务器（SCP / Git）。假设路径为 `~/mock_court_system`：

```bash
cd ~/mock_court_system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# 可复现：pip install -r requirements.lock
npm install
cp .env.example .env
# 填写 LLM_API_KEY、BACKEND_URL、NEXT_PUBLIC_BACKEND_URL 等
```

生产环境建议设置 `API_TOKEN`，并仅在需要局域网访问时设 `API_HOST=0.0.0.0`。

## 3. 启动后端（FastAPI）

### 直接运行（调试）

```bash
python api_server.py
```

默认监听 `127.0.0.1:8000`。Swagger：`http://<host>:8000/docs`。

### 后台运行

```bash
nohup python api_server.py > server.log 2>&1 &
tail -f server.log
```

### Systemd（生产）

`/etc/systemd/system/lexgentium-api.service`：

```ini
[Unit]
Description=LexGentium FastAPI
After=network.target

[Service]
User=root
WorkingDirectory=/root/mock_court_system
Environment="PATH=/root/mock_court_system/venv/bin"
ExecStart=/root/mock_court_system/venv/bin/python api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lexgentium-api
```

## 4. 前端

**只部署 FastAPI 时，浏览器工作台不会出现。** 请另起 Next，或用 Nginx 把 `/` 指到 `next start`，把 `/api` 反代到 Next（Next 再代理 FastAPI）。

```bash
cd ~/mock_court_system
npm run build
npx next start -p 3000
```

Next 服务端代理读 `BACKEND_URL`（默认 `http://localhost:8000`）。浏览器里的 Swagger 链接读 `NEXT_PUBLIC_BACKEND_URL`。

## 5. 验证

```bash
curl http://localhost:8000/health
# 工作台：http://localhost:3000/conversation
# 无状态调试（不经 Next）：
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"scenario":"CD","case_id":"test_001","dialog_history":[{"turn":0,"role":"Client","message":"你好"}]}'
```

不要再写或提交 `submission.json`；评测提交配置已不在本仓库。
