"""
자동 매매 실행 모듈 - 시그널 기반 매수/매도 자동 처리
"""
import time
from datetime import datetime

from broker import Broker
from signal_generator import compute_indicators, check_buy_signal, scan_universe
from risk_manager import (
    can_open_new_position, calculate_position_size,
    add_position, remove_position, check_positions_for_exit,
    print_portfolio_status, load_positions
)
from trade_logger import log_trade, log_daily_summary
from config import RISK


class AutoTrader:
    """자동매매 실행기"""

    def __init__(self, watchlist=None):
        self.broker = Broker()
        self.watchlist = watchlist or []
        self.trades_today = 0

    def set_watchlist(self, tickers):
        """감시 종목 설정"""
        self.watchlist = tickers
        print(f"[Trader] 감시 종목 {len(tickers)}개 설정")

    def run_sell_check(self):
        """
        보유 종목 매도 조건 확인 및 실행

        Returns:
            int: 매도 처리된 종목 수
        """
        print(f"\n[Trader] === 매도 체크 시작 ({datetime.now().strftime('%H:%M:%S')}) ===")

        exit_list = check_positions_for_exit(self.broker)
        sold_count = 0

        for item in exit_list:
            ticker = item["ticker"]
            qty = item["qty"]
            reason = item["reason"]

            print(f"  [매도대상] {ticker}: {reason}")

            # 시장가 매도
            result = self.broker.sell_market_order(ticker, qty)

            if result["success"]:
                # 현재가로 기록 (실제 체결가는 약간 다를 수 있음)
                price_info = self.broker.get_current_price(ticker)
                sell_price = price_info["price"] if price_info else item["entry_price"]

                log_trade(
                    ticker=ticker,
                    action="SELL",
                    qty=qty,
                    price=sell_price,
                    reason=reason,
                    order_no=result["order_no"],
                )
                remove_position(ticker)
                sold_count += 1
                self.trades_today += 1
            else:
                log_trade(
                    ticker=ticker,
                    action="SELL",
                    qty=qty,
                    price=0,
                    reason=f"실패: {result['message']}",
                    status="failed",
                )

            time.sleep(0.5)  # API 호출 간격

        if sold_count == 0:
            print("  매도 대상 없음")
        else:
            print(f"  {sold_count}종목 매도 완료")

        return sold_count

    def run_buy_check(self):
        """
        매수 시그널 스캔 및 실행

        Returns:
            int: 매수 처리된 종목 수
        """
        print(f"\n[Trader] === 매수 체크 시작 ({datetime.now().strftime('%H:%M:%S')}) ===")

        # 매수 가능 여부 확인
        can_buy = can_open_new_position(self.broker)
        if not can_buy["allowed"]:
            print(f"  매수 불가: {can_buy['reason']}")
            return 0

        # 이미 보유 중인 종목 제외
        holdings = set(load_positions().keys())
        scan_list = [t for t in self.watchlist if t not in holdings]

        if not scan_list:
            print("  스캔 대상 종목 없음")
            return 0

        # 시그널 스캔
        print(f"  {len(scan_list)}종목 스캔 중...")
        candidates = scan_universe(self.broker, scan_list)

        if not candidates:
            print("  매수 시그널 없음")
            return 0

        # RSI가 가장 낮은 순으로 정렬 (과매도 강도)
        candidates.sort(key=lambda x: x["rsi"])

        bought_count = 0
        balance = self.broker.get_balance()
        available_cash = balance["cash"]

        for cand in candidates:
            # 매수 가능 여부 재확인
            can_buy = can_open_new_position(self.broker)
            if not can_buy["allowed"]:
                print(f"  추가 매수 중단: {can_buy['reason']}")
                break

            ticker = cand["ticker"]
            price = cand["price"]
            stop_loss = cand["stop_loss"]

            # 포지션 사이즈 계산
            size = calculate_position_size(price, stop_loss, capital=available_cash)
            qty = size["qty"]

            if qty <= 0:
                print(f"  {ticker}: 매수 수량 0 → 스킵")
                continue

            print(f"  [매수실행] {ticker}: {qty}주 @ ~{price:,}원 "
                  f"(리스크 {size['risk_amount']:,}원, {size['risk_pct']:.1f}%)")

            # 시장가 매수
            result = self.broker.buy_market_order(ticker, qty)

            if result["success"]:
                log_trade(
                    ticker=ticker,
                    action="BUY",
                    qty=qty,
                    price=price,
                    stop_loss=stop_loss,
                    reason=f"RSI={cand['rsi']:.1f}",
                    order_no=result["order_no"],
                )
                add_position(ticker, price, qty, stop_loss)
                bought_count += 1
                self.trades_today += 1
                available_cash -= size["invested"]
            else:
                log_trade(
                    ticker=ticker,
                    action="BUY",
                    qty=qty,
                    price=price,
                    reason=f"실패: {result['message']}",
                    status="failed",
                )

            time.sleep(0.5)

        print(f"  {bought_count}종목 매수 완료")
        return bought_count

    def run_trading_cycle(self):
        """
        한 사이클 전체 매매 실행 (매도 → 매수 순서)

        Returns:
            dict: 실행 결과 요약
        """
        print(f"\n{'='*55}")
        print(f"  자동매매 사이클 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*55}")

        self.trades_today = 0

        # 1단계: 보유종목 매도 체크 (먼저 매도해서 현금 확보)
        sold = self.run_sell_check()

        # 2단계: 신규 매수 체크
        bought = self.run_buy_check()

        # 3단계: 포트폴리오 현황
        print_portfolio_status(self.broker)

        # 4단계: 일일 요약 로깅
        balance = self.broker.get_balance()
        log_daily_summary(
            total_eval=balance["total_eval"],
            cash=balance["cash"],
            total_pnl=balance["total_pnl"],
            positions_count=len(balance["positions"]),
            trades_today=self.trades_today,
        )

        result = {
            "sold": sold,
            "bought": bought,
            "total_trades": self.trades_today,
            "portfolio_value": balance["total_eval"],
        }

        print(f"\n  사이클 완료: 매도 {sold}건, 매수 {bought}건")
        print(f"{'='*55}\n")

        return result

    def run_stop_check(self):
        """
        손절만 빠르게 체크 (장중 주기적 실행용)
        """
        positions = load_positions()
        if not positions:
            return

        for ticker, pos in positions.items():
            try:
                price_info = self.broker.get_current_price(ticker)
                if not price_info:
                    continue

                current_low = price_info["low"]
                stop_loss = pos["stop_loss"]

                if current_low <= stop_loss:
                    print(f"  [긴급손절] {ticker}: 저가 {current_low:,} <= 손절 {stop_loss:,.0f}")
                    qty = pos["qty"]
                    result = self.broker.sell_market_order(ticker, qty)

                    if result["success"]:
                        log_trade(ticker, "SELL", qty, current_low,
                                  reason="긴급손절", order_no=result["order_no"])
                        remove_position(ticker)

                time.sleep(0.3)
            except Exception as e:
                print(f"  [손절체크] {ticker} 오류: {e}")
