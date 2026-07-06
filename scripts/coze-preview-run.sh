#!/usr/bin/env bash
set -euo pipefail

# 基于脚本位置定位项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 显式声明关键环境变量
export PORT=5000

# 清理 5000 端口残留进程（绝不碰 9000）
pid_5000=$(ss -lptn 'sport = :5000' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
if [ -n "$pid_5000" ]; then
  kill "$pid_5000" 2>/dev/null || true
  sleep 1
fi

# 清理 8000 端口残留进程（后端）
pid_8000=$(ss -lptn 'sport = :8000' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
if [ -n "$pid_8000" ]; then
  kill "$pid_8000" 2>/dev/null || true
  sleep 1
fi

# --- 启动后端 (FastAPI, port 8000, 后台) ---
cd backend
export SQLALCHEMY_DATABASE_URL="sqlite:///./mdm_governance.db"
export OM_ENABLED=false
export BTP_ENABLED=false
export ENV=development
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/mdm-backend.log 2>&1 &
cd "$PROJECT_DIR"

# 等待后端就绪
for i in $(seq 1 15); do
  if curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://localhost:8000/ 2>/dev/null | grep -q '200'; then
    echo "[coze-preview-run] backend ready"
    break
  fi
  sleep 1
done

# --- 启动前端 (Vite dev server, port 5000, 前台) ---
exec pnpm exec vite --host 0.0.0.0 --port 5000
