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
export ENV=development

# 启动 FastAPI（同时服务 API 和 SPA 静态文件），端口 5000
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 5000
