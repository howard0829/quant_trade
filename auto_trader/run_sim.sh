#!/bin/bash
# ─────────────────────────────────────────────
#  로컬 시뮬레이션 (API 연결 불필요)
#  pykrx 데이터로 가상 매매, 계좌 개설 필요 없음
# ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/homebrew/bin/python3.10"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/sim_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "===== 시뮬레이션 시작: $(date) =====" | tee -a "$LOG_FILE"
echo "  모드: 로컬 시뮬레이션 (API 연결 없음)" | tee -a "$LOG_FILE"
echo "  로그: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

case "${1:-run}" in
  test)
    $PYTHON main.py --sim --test 2>&1 | tee -a "$LOG_FILE"
    ;;
  once)
    $PYTHON main.py --sim --once 2>&1 | tee -a "$LOG_FILE"
    ;;
  status)
    $PYTHON main.py --sim --status 2>&1 | tee -a "$LOG_FILE"
    ;;
  history)
    $PYTHON main.py --sim --history 2>&1 | tee -a "$LOG_FILE"
    ;;
  reset)
    $PYTHON main.py --sim --reset 2>&1 | tee -a "$LOG_FILE"
    ;;
  run)
    $PYTHON main.py --sim --run 2>&1 | tee -a "$LOG_FILE"
    ;;
  *)
    echo "사용법: ./run_sim.sh [test|once|status|history|reset|run]"
    echo "  test    - 데이터 조회 테스트"
    echo "  once    - 1회 매매 사이클"
    echo "  status  - 포트폴리오 현황"
    echo "  history - 거래 내역"
    echo "  reset   - 초기화 (1000만원)"
    echo "  run     - 스케줄러 자동 실행 (기본값)"
    ;;
esac
