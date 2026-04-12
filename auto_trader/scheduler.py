"""
스케줄러 모듈 - 정해진 시각에 자동매매 실행

매매 스케줄:
  09:05 - 장 개장 확인 + 포트폴리오 현황
  10분마다 - 손절 체크 (장중)
  15:00 - 매매 시그널 체크 + 매도/매수 실행
  15:25 - 최종 상태 확인
"""
import schedule
import time
from datetime import datetime

from trader import AutoTrader
from risk_manager import print_portfolio_status
from trade_logger import print_recent_trades
from config import SIGNAL_CHECK_TIME, STOP_CHECK_INTERVAL_MIN


def is_trading_day():
    """오늘이 거래일인지 확인 (주말 제외, 공휴일은 미처리)"""
    today = datetime.now()
    return today.weekday() < 5  # 월(0)~금(4)


def is_trading_hours():
    """현재 장 시간인지 확인"""
    now = datetime.now()
    return 9 <= now.hour < 16  # 09:00 ~ 15:30 (여유 포함)


class TradingScheduler:
    """자동매매 스케줄러"""

    def __init__(self, watchlist=None):
        self.trader = AutoTrader(watchlist=watchlist)

    def job_morning_check(self):
        """장 시작 시 포트폴리오 현황 확인"""
        if not is_trading_day():
            print("[Schedule] 오늘은 휴장일입니다")
            return

        print(f"\n[Schedule] 장 시작 체크 - {datetime.now().strftime('%H:%M')}")
        print_portfolio_status(self.trader.broker)

    def job_stop_check(self):
        """장중 손절 체크"""
        if not is_trading_day() or not is_trading_hours():
            return

        self.trader.run_stop_check()

    def job_trading_cycle(self):
        """메인 매매 사이클"""
        if not is_trading_day():
            print("[Schedule] 오늘은 휴장일입니다")
            return

        print(f"\n[Schedule] 매매 사이클 실행 - {datetime.now().strftime('%H:%M')}")
        self.trader.run_trading_cycle()

    def job_closing_check(self):
        """장 마감 전 최종 확인"""
        if not is_trading_day():
            return

        print(f"\n[Schedule] 장 마감 체크 - {datetime.now().strftime('%H:%M')}")
        print_portfolio_status(self.trader.broker)
        print_recent_trades(5)

    def setup_schedule(self):
        """스케줄 설정"""
        # 장 시작 체크
        schedule.every().day.at("09:05").do(self.job_morning_check)

        # 손절 체크 (장중 10분마다)
        schedule.every(STOP_CHECK_INTERVAL_MIN).minutes.do(self.job_stop_check)

        # 메인 매매 사이클 (기본 15:00)
        schedule.every().day.at(SIGNAL_CHECK_TIME).do(self.job_trading_cycle)

        # 장 마감 전 최종 확인
        schedule.every().day.at("15:25").do(self.job_closing_check)

        print(f"[Schedule] 스케줄 설정 완료:")
        print(f"  09:05     - 장 시작 포트폴리오 확인")
        print(f"  {STOP_CHECK_INTERVAL_MIN}분 간격  - 손절 체크")
        print(f"  {SIGNAL_CHECK_TIME}    - 매매 시그널 체크 + 주문")
        print(f"  15:25     - 장 마감 전 최종 확인")

    def job_shutdown(self):
        """장 마감 후 프로세스 종료"""
        print(f"\n[Schedule] 장 마감 - 봇 종료 ({datetime.now().strftime('%H:%M')})")
        self._running = False

    def run(self):
        """스케줄 실행 (장 마감 시 자동 종료)"""
        self._running = True
        self.setup_schedule()

        # 15:35에 자동 종료
        schedule.every().day.at("15:35").do(self.job_shutdown)

        print(f"\n[Schedule] 자동매매 스케줄러 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print("  15:35에 자동 종료됩니다. 수동 종료: Ctrl+C\n")

        try:
            while self._running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        print("[Schedule] 스케줄러 종료")
