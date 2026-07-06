#!/usr/bin/env bash
set -euo pipefail

# 基于脚本位置定位项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# --- 前端依赖 ---
pnpm install

# --- 后端 Python 依赖 ---
# 使用 uv 管理依赖安装（系统级），避免 venv 创建超时
uv pip install --system -r backend/requirements.txt

# --- 初始化数据库 (SQLite) ---
cd backend
export SQLALCHEMY_DATABASE_URL="sqlite:///./mdm_governance.db"
export OM_ENABLED=false
export BTP_ENABLED=false
export ENV=development
python3 init_db.py

cd "$PROJECT_DIR"
echo "[coze-preview-build] done"
