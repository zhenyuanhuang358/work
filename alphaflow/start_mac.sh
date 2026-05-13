#!/bin/bash
set -e

echo ""
echo "╔═══════════════════════════════╗"
echo "║     AlphaFlow — 启动中...     ║"
echo "╚═══════════════════════════════╝"
echo ""

# 1. 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "正在安装 Python..."
  brew install python
fi

# 2. 定位项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 3. 安装依赖
echo "安装依赖..."
pip3 install -r backend/requirements.txt -q

# 4. 设置环境变量
export GOOGLE_API_KEY="AIzaSyA0O6NFH_Co1GY2q1TihOt7vNv2_f5fRHM"
export FMP_API_KEY="DraQiOzkvaGpIKoOQxy6VBfrRPNMPgNk"
export REPORTS_DIR="/tmp/alphaflow_reports"
mkdir -p "$REPORTS_DIR"

# 5. 启动后端
echo ""
echo "✓ 启动后端服务..."
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2

# 6. 打开界面
echo "✓ 打开浏览器界面..."
open "$SCRIPT_DIR/index.html"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  AlphaFlow 已启动！                      ║"
echo "║  浏览器界面已打开，输入股票代码即可使用  ║"
echo "║  按 Ctrl+C 停止服务                      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 等待
wait $BACKEND_PID
