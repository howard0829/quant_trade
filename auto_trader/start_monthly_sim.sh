#!/bin/bash
# ═══════════════════════════════════════════════════════
#  1개월 시뮬레이션 자동매매 - 원클릭 시작
#
#  맥북 덮개를 닫아도 매일 자동으로 실행됩니다.
#  전원 케이블을 반드시 연결해 두세요.
#
#  실행: ./start_monthly_sim.sh
#  중지: ./start_monthly_sim.sh stop
# ═══════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.howard.autotrader.plist"

# ── 중지 명령 ──
if [ "$1" = "stop" ]; then
    echo ""
    echo "  자동매매 시뮬레이션을 중지합니다..."
    echo ""

    # launchd 해제
    launchctl unload "$PLIST" 2>/dev/null
    echo "  [1/3] 스케줄러 해제 완료"

    # 예약 깨우기 해제
    sudo pmset repeat cancel 2>/dev/null
    echo "  [2/3] 예약 깨우기 해제 완료"

    # 잠자기 방지 해제
    sudo pmset disablesleep 0 2>/dev/null
    echo "  [3/3] 잠자기 방지 해제 완료"

    echo ""
    echo "  모든 자동매매가 중지되었습니다."
    echo "  시뮬레이션 결과 확인: ./run_sim.sh status"
    echo ""
    exit 0
fi

# ── 시작 ──
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   1개월 시뮬레이션 자동매매 설정                    ║"
echo "║   맥북 덮개를 닫아도 매일 자동 실행됩니다           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: 데이터 조회 테스트 ──
echo "  [1/5] 데이터 조회 테스트..."
cd "$SCRIPT_DIR"
TEST_RESULT=$(/opt/homebrew/bin/python3.10 main.py --sim --test 2>&1)
if echo "$TEST_RESULT" | grep -q "테스트 성공"; then
    echo "        데이터 조회 정상"
else
    echo "        데이터 조회 실패 - 네트워크를 확인하세요"
    echo "$TEST_RESULT"
    exit 1
fi

# ── Step 2: 시뮬레이션 초기화 여부 확인 ──
if [ -f "$SCRIPT_DIR/logs/sim_portfolio.json" ]; then
    echo ""
    echo "  기존 시뮬레이션 포트폴리오가 있습니다."
    read -p "  초기화하시겠습니까? (y/n, 기본 n): " RESET
    if [ "$RESET" = "y" ]; then
        /opt/homebrew/bin/python3.10 main.py --sim --reset 2>/dev/null
        echo "  [2/5] 포트폴리오 초기화 완료 (1,000만원)"
    else
        echo "  [2/5] 기존 포트폴리오 유지"
    fi
else
    echo "  [2/5] 새 포트폴리오 생성 (1,000만원)"
fi

# ── Step 3: macOS 잠자기 방지 (전원 연결 시) ──
echo ""
echo "  [3/5] macOS 잠자기 방지 설정 (관리자 권한 필요)..."
echo "        전원 케이블이 연결되어 있는지 확인하세요."
echo ""

# 전원 연결 시 잠자기 방지
sudo pmset -c displaysleep 5    # 디스플레이만 5분 후 끔
sudo pmset -c sleep 0            # 시스템 잠자기 비활성화 (전원 연결 시)
sudo pmset -c disksleep 0        # 디스크 잠자기 비활성화

echo "        전원 연결 시 시스템 잠자기 비활성화 완료"
echo "        (배터리 모드에서는 정상적으로 잠자기 됩니다)"

# ── Step 4: 예약 깨우기 설정 (백업) ──
echo "  [4/5] 평일 08:50 예약 깨우기 설정..."
sudo pmset repeat wakeorpoweron MTWRF 08:50:00
echo "        매주 월~금 08:50에 자동 깨우기 설정 완료"

# ── Step 5: launchd 스케줄 등록 ──
echo "  [5/5] 자동 실행 스케줄 등록..."
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo "        매일 08:55 시뮬레이션 자동 시작 등록 완료"

# ── 완료 ──
echo ""
echo "═══════════════════════════════════════════════════"
echo "  설정 완료!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  [동작 방식]"
echo "    매일 월~금 08:50  맥북 자동 깨어남"
echo "    08:55             시뮬레이션 봇 자동 시작"
echo "    09:05             포트폴리오 현황 확인"
echo "    10분마다          보유종목 손절 체크"
echo "    15:00             매도/매수 시그널 체크 + 주문"
echo "    15:25             장 마감 최종 확인 + 일간 리포트"
echo "    15:35             봇 자동 종료"
echo ""
echo "  [확인 명령어]"
echo "    ./run_sim.sh status           포트폴리오 현황"
echo "    ./run_sim.sh history          거래 내역"
echo "    cat logs/daily_reports/*.md   일간 리포트"
echo "    tail -f logs/sim_*.log        실시간 로그"
echo ""
echo "  [중지]"
echo "    ./start_monthly_sim.sh stop   모든 자동매매 중지 + 설정 복원"
echo ""
echo "  이제 맥북 덮개를 닫으셔도 됩니다."
echo "  전원 케이블은 반드시 연결해 두세요."
echo ""
