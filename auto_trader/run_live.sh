#!/bin/bash
# ─────────────────────────────────────────────
#  실전매매 자동매매 (KIS_MOCK=false 강제)
#  ⚠️  실제 돈이 투입됩니다!
# ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/homebrew/bin/python3.10"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/live_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

export KIS_MOCK=false

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ⚠️  실전매매 모드 - 실제 돈이 투입됩니다  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 실전 실행 전 확인
if [ "${1}" != "--yes" ] && [ "${2}" != "--yes" ]; then
  read -p "  정말 실전매매를 시작하시겠습니까? (yes 입력): " CONFIRM
  if [ "$CONFIRM" != "yes" ]; then
    echo "  취소됨"
    exit 0
  fi
fi

echo "===== 실전매매 봇 시작: $(date) =====" | tee -a "$LOG_FILE"
echo "  모드: ⚠️  실전매매 (LIVE)" | tee -a "$LOG_FILE"
echo "  로그: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

case "${1:-run}" in
  test)
    $PYTHON main.py --test 2>&1 | tee -a "$LOG_FILE"
    ;;
  once)
    $PYTHON main.py --once 2>&1 | tee -a "$LOG_FILE"
    ;;
  status)
    $PYTHON main.py --status 2>&1 | tee -a "$LOG_FILE"
    ;;
  history)
    $PYTHON main.py --history 2>&1 | tee -a "$LOG_FILE"
    ;;
  run)
    $PYTHON main.py --run 2>&1 | tee -a "$LOG_FILE"
    ;;
  *)
    echo "사용법: ./run_live.sh [test|once|status|history|run] [--yes]"
    echo "  test    - API 접속 테스트"
    echo "  once    - 1회 매매 사이클"
    echo "  status  - 포트폴리오 현황"
    echo "  history - 거래 내역"
    echo "  run     - 스케줄러 자동 실행 (기본값)"
    echo "  --yes   - 확인 프롬프트 생략"
    ;;
esac
