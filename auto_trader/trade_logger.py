"""
거래 기록 로깅 모듈 - CSV 파일로 모든 거래 내역 기록
"""
import csv
import os
from datetime import datetime
from pathlib import Path
from config import LOG_DIR


TRADE_LOG_FILE = LOG_DIR / "trades.csv"
DAILY_LOG_FILE = LOG_DIR / "daily_summary.csv"

TRADE_HEADERS = [
    "timestamp", "ticker", "action", "qty", "price", "amount",
    "stop_loss", "reason", "order_no", "status"
]

DAILY_HEADERS = [
    "date", "total_eval", "cash", "total_pnl", "pnl_pct",
    "positions_count", "trades_today", "signals_found"
]


def _ensure_csv(filepath, headers):
    """CSV 파일이 없으면 헤더와 함께 생성"""
    if not filepath.exists():
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)


def log_trade(ticker, action, qty, price, stop_loss=0,
              reason="", order_no="", status="success"):
    """
    거래 내역 기록

    Parameters:
        ticker: 종목코드
        action: "BUY" 또는 "SELL"
        qty: 수량
        price: 가격
        stop_loss: 손절가 (매수 시)
        reason: 매매 사유
        order_no: 주문번호
        status: "success" 또는 "failed"
    """
    _ensure_csv(TRADE_LOG_FILE, TRADE_HEADERS)

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ticker,
        action,
        qty,
        price,
        qty * price,
        stop_loss,
        reason,
        order_no,
        status,
    ]

    with open(TRADE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    print(f"[Log] {action} {ticker} x {qty}주 @ {price:,}원 ({reason})")


def log_daily_summary(total_eval, cash, total_pnl, positions_count,
                      trades_today=0, signals_found=0):
    """일일 요약 기록"""
    _ensure_csv(DAILY_LOG_FILE, DAILY_HEADERS)

    capital = total_eval if total_eval > 0 else 10_000_000
    pnl_pct = total_pnl / capital * 100

    row = [
        datetime.now().strftime("%Y-%m-%d"),
        total_eval,
        cash,
        total_pnl,
        round(pnl_pct, 2),
        positions_count,
        trades_today,
        signals_found,
    ]

    with open(DAILY_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def get_trade_history(last_n=20):
    """최근 거래 내역 조회"""
    if not TRADE_LOG_FILE.exists():
        return []

    with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    return rows[-last_n:] if len(rows) > last_n else rows


def print_recent_trades(n=10):
    """최근 거래 출력"""
    trades = get_trade_history(n)
    if not trades:
        print("  거래 내역 없음")
        return

    print(f"\n  최근 {len(trades)}건 거래 내역:")
    print(f"  {'일시':19s} {'종목':8s} {'매매':4s} {'수량':>5s} {'가격':>10s} {'사유'}")
    print(f"  {'─'*60}")
    for t in trades:
        print(f"  {t['timestamp']} {t['ticker']:8s} {t['action']:4s} "
              f"{t['qty']:>5s} {int(t['price']):>9,}원 {t['reason'][:20]}")
