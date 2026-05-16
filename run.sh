#!/usr/bin/env bash
# Sequoia-X 一键运行脚本
# 用法:
#   ./run.sh              # 日常模式：增量 + 选股 + 飞书推送
#   ./run.sh --backfill   # 回填模式：全市场历史K线
#   ./run.sh --dry-run    # 仅选股，不推送飞书

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# 确保 .env 存在
if [ ! -f .env ]; then
    echo "❌ 缺少 .env 文件，请从 .env.example 复制并配置飞书 Webhook" >&2
    exit 1
fi

# 日志输出到 data/ 目录
mkdir -p data
LOG_FILE="data/run_$(date +%Y%m%d_%H%M%S).log"

BACKFILL=""
DRY_RUN=""

case "${1:-}" in
    --backfill)
        BACKFILL="--backfill"
        ;;
    --dry-run)
        DRY_RUN="1"
        ;;
esac

if [ -n "$BACKFILL" ]; then
    echo "=== Sequoia-X 回填模式 ===" | tee -a "$LOG_FILE"
    python3 main.py --backfill 2>&1 | tee -a "$LOG_FILE"
else
    if [ -n "$DRY_RUN" ]; then
        echo "=== Sequoia-X 选股（不推送） ===" | tee -a "$LOG_FILE"
        # 运行选股逻辑但跳过飞书推送：用环境变量覆盖 webhook 为空
        FEISHU_WEBHOOK_URL="" python3 main.py 2>&1 | tee -a "$LOG_FILE" || true
    else
        echo "=== Sequoia-X 日常模式 ===" | tee -a "$LOG_FILE"
        python3 main.py 2>&1 | tee -a "$LOG_FILE"
    fi
fi

EXIT_CODE=${PIPESTATUS[0]}
echo "退出码: $EXIT_CODE" | tee -a "$LOG_FILE"
exit $EXIT_CODE
