"""
거래 기록 로깅 모듈 - CSV + 일간 Markdown 리포트
"""
import csv
import os
from datetime import datetime
from pathlib import Path
from config import LOG_DIR, RISK, STRATEGY


TRADE_LOG_FILE = LOG_DIR / "trades.csv"
DAILY_LOG_FILE = LOG_DIR / "daily_summary.csv"
REPORT_DIR = LOG_DIR / "daily_reports"
REPORT_DIR.mkdir(exist_ok=True)

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


# ─────────────────────────────────────────────
# 일간 Markdown 리포트
# ─────────────────────────────────────────────

def generate_daily_report(balance, positions_detail, trades_today_list,
                          signals_found=0, sold_count=0, bought_count=0):
    """
    일간 Markdown 리포트 생성 및 저장

    Parameters:
        balance: broker.get_balance() 결과
        positions_detail: risk_manager.load_positions() 결과
        trades_today_list: 오늘 발생한 거래 목록 (get_today_trades() 결과)
        signals_found: 스캔에서 발견된 매수 시그널 수
        sold_count: 오늘 매도 건수
        bought_count: 오늘 매수 건수

    Returns:
        str: 저장된 리포트 파일 경로
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    filename = f"daily_{today.strftime('%Y%m%d')}.md"
    filepath = REPORT_DIR / filename

    cash = balance.get("cash", 0)
    total_eval = balance.get("total_eval", 0)
    total_pnl = balance.get("total_pnl", 0)
    positions = balance.get("positions", [])
    capital = RISK["total_capital"]
    pnl_pct = total_pnl / capital * 100 if capital > 0 else 0

    lines = []
    lines.append(f"# 일간 매매 리포트 - {date_str}")
    lines.append("")
    lines.append(f"**생성시각**: {today.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**모드**: {'모의투자' if os.environ.get('KIS_MOCK', 'true').lower() == 'true' else '실전매매'}")
    lines.append(f"**전략**: RSI({STRATEGY['rsi_period']}) < {STRATEGY['rsi_threshold']}, "
                 f"SMA({STRATEGY['trend_sma_period']}), 청산 SMA({STRATEGY['exit_sma_period']})")
    lines.append("")

    # ── 포트폴리오 요약 ──
    lines.append("## 포트폴리오 요약")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|------|-----|")
    lines.append(f"| 총평가금액 | {total_eval:,}원 |")
    lines.append(f"| 예수금 | {cash:,}원 |")
    lines.append(f"| 총손익 | {total_pnl:+,}원 ({pnl_pct:+.2f}%) |")
    lines.append(f"| 보유종목 | {len(positions)}개 / {RISK['max_positions']}개 |")
    lines.append(f"| 오늘 매수 | {bought_count}건 |")
    lines.append(f"| 오늘 매도 | {sold_count}건 |")
    lines.append(f"| 매수 시그널 | {signals_found}개 발견 |")
    lines.append("")

    # ── 보유 종목 현황 ──
    lines.append("## 보유 종목 현황")
    lines.append("")
    if positions:
        lines.append("| 종목 | 수량 | 평균가 | 현재가 | 손익률 | 매수일 | 손절가 |")
        lines.append("|------|------|--------|--------|--------|--------|--------|")
        for p in positions:
            ticker = p.get("ticker", "")
            name = p.get("name", ticker)
            pos_info = positions_detail.get(ticker, {})
            entry_date = pos_info.get("entry_date", "-")
            stop_loss = pos_info.get("stop_loss", 0)
            sl_str = f"{stop_loss:,.0f}원" if stop_loss else "-"
            lines.append(
                f"| {name} ({ticker}) | {p['qty']}주 | {p['avg_price']:,}원 | "
                f"{p['current_price']:,}원 | {p['pnl_pct']:+.1f}% | {entry_date} | {sl_str} |"
            )
    else:
        lines.append("보유 종목 없음")
    lines.append("")

    # ── 오늘 거래 내역 ──
    lines.append("## 오늘 거래 내역")
    lines.append("")
    if trades_today_list:
        lines.append("| 시각 | 종목 | 매매 | 수량 | 가격 | 금액 | 사유 |")
        lines.append("|------|------|------|------|------|------|------|")
        for t in trades_today_list:
            amt = int(t.get("amount", 0))
            price = int(float(t.get("price", 0)))
            lines.append(
                f"| {t['timestamp'][11:]} | {t['ticker']} | {t['action']} | "
                f"{t['qty']}주 | {price:,}원 | {amt:,}원 | {t.get('reason', '')} |"
            )
    else:
        lines.append("오늘 거래 없음")
    lines.append("")

    # ── 누적 성과 ──
    all_trades = get_trade_history(9999)
    if all_trades:
        total_count = len(all_trades)
        buys = [t for t in all_trades if t["action"] == "BUY"]
        sells = [t for t in all_trades if t["action"] == "SELL"]
        success = [t for t in all_trades if t.get("status") == "success"]

        lines.append("## 누적 성과")
        lines.append("")
        lines.append("| 항목 | 값 |")
        lines.append("|------|-----|")
        lines.append(f"| 총 거래 수 | {total_count}건 (매수 {len(buys)}, 매도 {len(sells)}) |")
        lines.append(f"| 성공 주문 | {len(success)}건 |")
        lines.append(f"| 운용 시작 자본 | {capital:,}원 |")
        lines.append(f"| 현재 총평가 | {total_eval:,}원 |")
        lines.append(f"| 누적 수익률 | {pnl_pct:+.2f}% |")
    lines.append("")

    # ── 저장 ──
    content = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[Log] 일간 리포트 저장: {filepath}")
    return str(filepath)


def get_today_trades():
    """오늘 날짜의 거래 내역만 반환"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    all_trades = get_trade_history(9999)
    return [t for t in all_trades if t.get("timestamp", "").startswith(today_str)]
