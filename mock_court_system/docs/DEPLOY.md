# 模拟法庭 API 服务部署指南

本指南介绍如何在 Ubuntu 云服务器上部署模拟法庭 API 服务。

## 1. 服务器准备

推荐配置：
- **操作系统**: Ubuntu 20.04 LTS 或 22.04 LTS
- **CPU/内存**: 2核 2GB 或 4GB
- **带宽**: 3Mbps+ (按流量计费更划算)
- **端口**: 需在安全组/防火墙开放 TCP 8000 端口

## 2. 环境搭建

连接到服务器后，执行以下命令安装 Python 环境：

```bash
# 更新软件源
sudo apt update

# 安装 Python3, pip, venv 和 git
sudo apt install python3-pip python3-venv git -y
```

## 3. 部署代码

将 `mock_court_multiagents` 文件夹上传到服务器（可以使用 SCP, FileZilla 或 Git）。

假设代码位于 `~/mock_court_multiagents`：

```bash
cd ~/mock_court_multiagents

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 4. 启动服务

### 方式一：直接运行 (测试用)

```bash
python api_server.py
```

### 方式二：后台运行 (推荐)

使用 `nohup` 让服务在后台运行：

```bash
# 启动服务并将日志输出到 server.log
nohup python api_server.py > server.log 2>&1 &

# 查看日志
tail -f server.log
```

### 方式三：使用 Systemd (生产环境推荐)

创建服务文件 `/etc/systemd/system/mock-court.service`:

```ini
[Unit]
Description=Mock Court API Service
After=network.target

[Service]
User=root
WorkingDirectory=/root/mock_court_multiagents
Environment="PATH=/root/mock_court_multiagents/venv/bin"
ExecStart=/root/mock_court_multiagents/venv/bin/python api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start mock-court
sudo systemctl enable mock-court
```

## 5. 验证服务

在本地或服务器上测试：

```bash
curl -X POST http://localhost:8000/ \
     -H "Content-Type: application/json" \
     -d '{
           "scenario": "CD",
           "case_id": "test_001",
           "dialog_history": [{"turn": 0, "role": "Client", "message": "你好"}]
         }'
```

## 6. 提交配置

修改 `submission.json`，将 `api_key` 替换为您的服务器公网 IP：

```json
{
    "api_key": "http://<服务器公网IP>:8000/",
    "headers": {
        "Content-Type": "application/json"
    }
}
```
