#!/usr/bin/env bash
# 一键启动（裸机模式）：python 后端 + 已构建前端
set -e
cd "$(dirname "$0")"
if [ ! -d frontend/dist ]; then
  echo "[start] 构建前端…"
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi
echo "[start] 可选 AI 依赖（faster-whisper/rembg/edge-tts）未安装时自动降级"
echo "[start] 启动 http://127.0.0.1:${PORT:-8000}"
cd backend && exec python run.py
