#!/usr/bin/env bash
# 一键启动脚本：首次运行自动创建虚拟环境并安装依赖
set -e
cd "$(dirname "$0")"

# 选择可用的 Python 解释器（优先 3.13/3.12，避开本机损坏的 3.14）
PY=""
for cand in python3.13 python3.12 python3; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then echo "未找到 Python3"; exit 1; fi

if [ ! -d ".venv" ]; then
  echo "创建虚拟环境（$PY）..."
  "$PY" -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

exec ./.venv/bin/python image_tools.py
