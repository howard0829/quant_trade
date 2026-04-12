"""
3일 단기매매 자동매매 봇 - 메인 실행 파일

사용법:
    # 시뮬레이션 (API 불필요 - pykrx 데이터 사용)
    python main.py --sim --test       # 데이터 조회 테스트
    python main.py --sim --once       # 1회 매매 사이��
    python main.py --sim --run        # 스케줄러 자동 실행
    python main.py --sim --status     # 포트폴리오 현황
    python main.py --sim --reset      # 시뮬레이션 초기화 (1000만원)

    # 모의투자 (한국투자증권 모의투자 서버)
    python main.py --test             # API 접속 테스트
    python main.py --once             # 1회 매매 사이클
    python main.py --run              # 스케줄러 자동 실행

    # 종목 리스트 지정
    python main.py --sim --once --tickers 005930,000660,035420
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import validate, print_config, MOCK_TRADING, WATCHLIST, RISK


def get_default_watchlist():
    """기본 감시 종목 (KOSPI + KOSDAQ 시총 상위)"""
    kospi = [
        "005930",  # 삼성전자
        "000660",  # SK하이닉스
        "005935",  # 삼성전자우
        "005380",  # 현대차
        "000270",  # 기아
        "068270",  # 셀트리온
        "035420",  # NAVER
        "005490",  # POSCO홀딩스
        "035720",  # 카카오
        "051910",  # LG화학
        "006400",  # 삼성SDI
        "028260",  # 삼성물산
        "003670",  # 포스코퓨처엠
        "105560",  # KB금융
        "055550",  # 신한지주
        "012330",  # 현대모비스
        "066570",  # LG전자
        "032830",  # 삼성생명
        "003550",  # LG
        "034730",  # SK
        "086790",  # 하나금융지주
        "096770",  # SK이노베이션
        "010130",  # 고려아연
        "015760",  # 한국전력
        "033780",  # KT&G
        "017670",  # SK텔레콤
        "009150",  # 삼성전기
        "030200",  # KT
        "034020",  # 두산에너빌리티
        "316140",  # 우리금융지주
    ]
    kosdaq = [
        "247540",  # 에코프로비엠
        "403870",  # HPSP
        "196170",  # 알테오젠
        "058470",  # 리노공업
        "041510",  # 에스엠
        "145020",  # 휴젤
        "112040",  # 위메이드
        "035900",  # JYP Ent.
        "293490",  # 카카오게임즈
        "377300",  # 카카오페이
        "352820",  # 하이브
        "263750",  # 펄어비스
        "328130",  # 루닛
        "086520",  # 에코프로
        "095340",  # ISC
        "357780",  # 솔브레인
        "036930",  # 주성엔지니어링
        "137310",  # 에스디바이오센서
        "039030",  # 이오테크닉스
        "067160",  # 아프리카TV
    ]
    return kospi + kosdaq


# ── 시뮬레이션 명령어 ──

def cmd_sim_test():
    """시뮬레이션 데이터 조회 테스트"""
    print("\n[Test] 로컬 시뮬레이션 테스트 (API 불필요)...")
    from sim_broker import SimBroker
    broker = SimBroker()

    price = broker.get_current_price("005930")
    if price:
        print(f"  삼성전자 최근 종가: {price['price']:,}원 ({price['change_pct']:+.2f}%)")
        print(f"  시가: {price['open']:,} | 고가: {price['high']:,} | "
              f"저가: {price['low']:,} | 거래량: {price['volume']:,}")
    else:
        print("  데이터 조회 실패 - 네트워크를 확인하세요")
        return

    balance = broker.get_balance()
    print(f"\n  시뮬레이션 예수금: {balance['cash']:,}원")
    print(f"  총평가: {balance['total_eval']:,}원")
    print(f"  보유종목: {len(balance['positions'])}개")
    print("\n  데이터 조회 테스트 성공!")


def cmd_sim_status():
    """시뮬레이션 포트폴리오 현황"""
    from sim_broker import SimBroker
    from risk_manager import print_portfolio_status
    from trade_logger import print_recent_trades

    broker = SimBroker()
    print_portfolio_status(broker)
    print_recent_trades(10)


def cmd_sim_once(watchlist):
    """시뮬레이션 1회 매매 사이클"""
    from trader import AutoTrader
    trader = AutoTrader(broker_mode="sim")
    trader.set_watchlist(watchlist)
    trader.run_trading_cycle()


def cmd_sim_run(watchlist):
    """시뮬레이션 스케줄러"""
    from scheduler import TradingScheduler
    scheduler = TradingScheduler(watchlist=watchlist, broker_mode="sim")
    scheduler.trader.set_watchlist(watchlist)
    scheduler.run()


def cmd_sim_reset():
    """시뮬레이션 포트폴리오 초기화"""
    from sim_broker import SimBroker
    broker = SimBroker()
    broker.reset()
    print(f"  시뮬레이션 포트폴리오가 {RISK['total_capital']:,}원으로 초기화되었습니다.")


# ── API 명령어 ──

def cmd_test():
    """API 접속 테스트"""
    print("\n[Test] API 접속 테스트...")
    from broker import Broker
    broker = Broker()

    price = broker.get_current_price("005930")
    if price:
        print(f"  삼성전자 현재가: {price['price']:,}원 ({price['change_pct']:+.2f}%)")
        print(f"  시가: {price['open']:,} | 고가: {price['high']:,} | "
              f"저가: {price['low']:,} | 거래량: {price['volume']:,}")
    else:
        print("  현재가 조회 실패 - API 키/네트워크를 확인하세요")
        return

    balance = broker.get_balance()
    print(f"\n  예수금: {balance['cash']:,}원")
    print(f"  총평가: {balance['total_eval']:,}원")
    print(f"  보유종목: {len(balance['positions'])}개")
    print("\n  API 접속 테스트 성공!")


def cmd_status():
    """API 포트폴리오 현황"""
    from broker import Broker
    from risk_manager import print_portfolio_status
    from trade_logger import print_recent_trades

    broker = Broker()
    print_portfolio_status(broker)
    print_recent_trades(10)


def cmd_once(watchlist):
    """API 1회 매매 사이클"""
    from trader import AutoTrader

    if not MOCK_TRADING:
        confirm = input("\n  실전매매 모드입니다. 정말 실행하시겠습니까? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소됨")
            return

    trader = AutoTrader(broker_mode="api")
    trader.set_watchlist(watchlist)
    trader.run_trading_cycle()


def cmd_run(watchlist):
    """API 스케줄러"""
    from scheduler import TradingScheduler

    if not MOCK_TRADING:
        confirm = input("\n  실전매매 모드입니다. 스케줄러를 시작하시겠습니까? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소됨")
            return

    scheduler = TradingScheduler(watchlist=watchlist, broker_mode="api")
    scheduler.trader.set_watchlist(watchlist)
    scheduler.run()


def cmd_history():
    """거래 내역"""
    from trade_logger import print_recent_trades
    print_recent_trades(30)


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="3일 단기매매 자동매매 봇")
    parser.add_argument("--sim", action="store_true",
                        help="로컬 시뮬레이션 모드 (API 불필요)")
    parser.add_argument("--test", action="store_true", help="접속/데이터 테스트")
    parser.add_argument("--status", action="store_true", help="포트폴리오 현황")
    parser.add_argument("--once", action="store_true", help="1회 매매 사이클 실행")
    parser.add_argument("--run", action="store_true", help="스케줄러 자동 실행")
    parser.add_argument("--history", action="store_true", help="거래 내역 조회")
    parser.add_argument("--reset", action="store_true", help="시뮬레이션 초기화")
    parser.add_argument("--tickers", default=None,
                        help="감시 종목 (쉼표 구분, 예: 005930,000660)")

    args = parser.parse_args()

    # 종목 리스트
    if args.tickers:
        watchlist = [t.strip() for t in args.tickers.split(",")]
    elif WATCHLIST:
        watchlist = WATCHLIST
    else:
        watchlist = get_default_watchlist()

    # ── 시뮬레이션 모드 ──
    if args.sim:
        os.environ["BROKER_MODE"] = "sim"
        print(f"\n  [모드] 로컬 시뮬레이션 (API 연결 없음)")
        print(f"  [자본] {RISK['total_capital']:,}원\n")

        if args.test:
            cmd_sim_test()
        elif args.status:
            cmd_sim_status()
        elif args.once:
            cmd_sim_once(watchlist)
        elif args.run:
            cmd_sim_run(watchlist)
        elif args.reset:
            cmd_sim_reset()
        elif args.history:
            cmd_history()
        else:
            print("  사용법:")
            print("    python main.py --sim --test     # 데이터 조회 테스트")
            print("    python main.py --sim --once     # 1회 매매 사이클")
            print("    python main.py --sim --run      # 스케줄러 자동 실행")
            print("    python main.py --sim --status   # 포트폴리오 현황")
            print("    python main.py --sim --history  # 거래 내역")
            print("    python main.py --sim --reset    # 초기화 (1000만원)")
        return

    # ── API 모드 (모의투자/실전) ──
    print_config()

    if not validate():
        print("\n.env 파일이 필요��니다. 시뮬레이션은 --sim 옵션을 사용하세요.")
        print(f"  시뮬레이션: python main.py --sim --test")
        print(f"  API 설정:   cp .env.example .env && vi .env")
        return

    if args.test:
        cmd_test()
    elif args.status:
        cmd_status()
    elif args.once:
        cmd_once(watchlist)
    elif args.run:
        cmd_run(watchlist)
    elif args.history:
        cmd_history()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
