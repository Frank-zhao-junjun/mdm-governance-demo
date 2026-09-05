#!/usr/bin/env bash
set -euo pipefail

# 基于脚本位置定位项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR/backend"

# 显式声明关键环境变量
export SQLALCHEMY_DATABASE_URL="sqlite:///./mdm_governance.db"
export OM_ENABLED=false
export BTP_ENABLED=false
export ENV=production

# JWT 密钥：优先使用平台注入的 MDM_SECRET_KEY；否则生成并持久化到本地文件（避免重启后 token 全部失效）
if [ -z "${MDM_SECRET_KEY:-}" ]; then
  KEY_FILE="$PROJECT_DIR/backend/.mdm_secret_key"
  if [ -f "$KEY_FILE" ]; then
    MDM_SECRET_KEY="$(cat "$KEY_FILE")"
  else
    MDM_SECRET_KEY="$(openssl rand -hex 32)"
    echo "$MDM_SECRET_KEY" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
  fi
fi
export MDM_SECRET_KEY

# 启动 FastAPI（同时服务 API 和 SPA 静态文件），端口 5000
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 5000
