"""
3일 단기매매 자동매매 봇 - 메인 실행 파일

사용법:
    # 1. .env 파일 설정 후 모의투자 테스트
    python main.py --test          # 접속 테스트
    python main.py --status        # 포트폴리오 현황
    python main.py --once          # 1회 매매 사이클 실행
    python main.py --run           # 스케줄러 자동 실행 (장중 상시)
    python main.py --history       # 최근 거래 내역

    # 2. 종목 리스트 지정
    python main.py --once --tickers 005930,000660,035420
"""
import sys
import os
import argparse

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import validate, print_config, MOCK_TRADING, WATCHLIST


def get_default_watchlist():
    """기본 감시 종목 (KOSPI + KOSDAQ 시총 상위)"""
    # KOSPI 상위 30
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
    # KOSDAQ 상위 20
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


def cmd_test():
    """접속 테스트"""
    print("\n[Test] API 접속 테스트...")
    from broker import Broker
    broker = Broker()

    # 삼성전자 현재가 조회
    price = broker.get_current_price("005930")
    if price:
        print(f"  삼성전자 현재가: {price['price']:,}원 ({price['change_pct']:+.2f}%)")
        print(f"  시가: {price['open']:,} | 고가: {price['high']:,} | "
              f"저가: {price['low']:,} | 거래량: {price['volume']:,}")
    else:
        print("  현재가 조회 실패 - API 키/네트워크를 확인하세요")
        return

    # 잔고 조회
    balance = broker.get_balance()
    print(f"\n  예수금: {balance['cash']:,}원")
    print(f"  총평가: {balance['total_eval']:,}원")
    print(f"  보유종목: {len(balance['positions'])}개")

    print("\n  ✅ API 접속 테스트 성공!")


def cmd_status():
    """포트폴리오 현황"""
    from broker import Broker
    from risk_manager import print_portfolio_status
    from trade_logger import print_recent_trades

    broker = Broker()
    print_portfolio_status(broker)
    print_recent_trades(10)


def cmd_once(watchlist):
    """1회 매매 사이클"""
    from trader import AutoTrader

    if not MOCK_TRADING:
        confirm = input("\n⚠️  실전매매 모드입니다. 정말 실행하시겠습니까? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소됨")
            return

    trader = AutoTrader()
    trader.set_watchlist(watchlist)
    trader.run_trading_cycle()


def cmd_run(watchlist):
    """스케줄러 자동 실행"""
    from scheduler import TradingScheduler

    if not MOCK_TRADING:
        confirm = input("\n⚠️  실전매매 모드입니다. 스케줄러를 시작하시겠습니까? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소됨")
            return

    scheduler = TradingScheduler(watchlist=watchlist)
    scheduler.trader.set_watchlist(watchlist)
    scheduler.run()


def cmd_history():
    """거래 내역"""
    from trade_logger import print_recent_trades
    print_recent_trades(30)


def main():
    parser = argparse.ArgumentParser(description="3일 단기매매 자동매매 봇")
    parser.add_argument("--test", action="store_true", help="API 접속 테스트")
    parser.add_argument("--status", action="store_true", help="포트폴리오 현황")
    parser.add_argument("--once", action="store_true", help="1회 매매 사이클 실행")
    parser.add_argument("--run", action="store_true", help="스케줄러 자동 실행")
    parser.add_argument("--history", action="store_true", help="거래 내역 조회")
    parser.add_argument("--tickers", default=None,
                        help="감시 종목 (쉼표 구분, 예: 005930,000660)")

    args = parser.parse_args()

    # 설정 출력
    print_config()

    # API 키 검증
    if not validate():
        print("\n.env.example 파일을 참고하여 .env 파일을 작성하세요.")
        print(f"  cp .env.example .env")
        print(f"  vi .env")
        return

    # 종목 리스트
    if args.tickers:
        watchlist = [t.strip() for t in args.tickers.split(",")]
    elif WATCHLIST:
        watchlist = WATCHLIST
    else:
        watchlist = get_default_watchlist()

    # 명령 실행
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
        print(f"\n  예시:")
        print(f"    python main.py --test          # 접속 테스트")
        print(f"    python main.py --once          # 1회 매매 실행")
        print(f"    python main.py --run           # 스케줄러 시작")


if __name__ == "__main__":
    main()
