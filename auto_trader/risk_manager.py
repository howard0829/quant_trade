"""
리스크 관리 모듈 - 포지션 사이징, 손절 관리, 일일 손실 한도
"""
import json
from pathlib import Path
from datetime import datetime, date
from config import RISK, STRATEGY, LOG_DIR


# 포지션 정보 파일 (보유기간, 손절가 등 추적)
POSITIONS_FILE = LOG_DIR / "positions.json"


def load_positions():
    """저장된 포지션 정보 로드"""
    if POSITIONS_FILE.exists():
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return {}


def save_positions(positions):
    """포지션 정보 저장"""
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2, ensure_ascii=False, default=str)


def add_position(ticker, entry_price, qty, stop_loss):
    """새 포지션 추가"""
    positions = load_positions()
    positions[ticker] = {
        "entry_date": datetime.now().strftime("%Y-%m-%d"),
        "entry_price": entry_price,
        "qty": qty,
        "stop_loss": stop_loss,
        "invested": entry_price * qty,
    }
    save_positions(positions)
    print(f"[Risk] 포지션 추가: {ticker} | {qty}주 @ {entry_price:,}원 | 손절 {stop_loss:,.0f}원")


def remove_position(ticker):
    """포지션 제거"""
    positions = load_positions()
    if ticker in positions:
        del positions[ticker]
        save_positions(positions)
        print(f"[Risk] 포지션 제거: {ticker}")


def get_position_info(ticker):
    """특정 종목 포지션 정보 조회"""
    positions = load_positions()
    return positions.get(ticker)


def calculate_position_size(entry_price, stop_loss, capital=None):
    """
    리스크 기반 포지션 사이즈 계산

    Parameters:
        entry_price: 매수 예정가
        stop_loss: 손절가
        capital: 총 자본 (None이면 설정값 사용)

    Returns:
        dict: {"qty": int, "invested": int, "risk_amount": int}
    """
    if capital is None:
        capital = RISK["total_capital"]

    # 종목당 최대 리스크 금액
    max_risk = capital * RISK["risk_per_trade_pct"] / 100

    # 종목당 최대 투자금액
    max_invest = capital * RISK["max_position_pct"] / 100

    # 주당 리스크
    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        print(f"[Risk] 손절가({stop_loss:,})가 매수가({entry_price:,}) 이상 → 매수 불가")
        return {"qty": 0, "invested": 0, "risk_amount": 0}

    # 리스크 기반 수량
    qty_by_risk = int(max_risk / risk_per_share)

    # 금액 기반 수량
    qty_by_amount = int(max_invest / entry_price)

    # 둘 중 작은 값
    qty = min(qty_by_risk, qty_by_amount)
    qty = max(qty, 0)  # 음수 방지

    invested = qty * entry_price
    risk_amount = qty * risk_per_share

    return {
        "qty": qty,
        "invested": invested,
        "risk_amount": risk_amount,
        "risk_pct": risk_amount / capital * 100 if capital > 0 else 0,
    }


def can_open_new_position(broker):
    """
    신규 포지션 개설 가능 여부 확인

    Returns:
        dict: {"allowed": bool, "reason": str, "available_cash": int}
    """
    positions = load_positions()
    current_count = len(positions)

    # 최대 포지션 수 확인
    if current_count >= RISK["max_positions"]:
        return {
            "allowed": False,
            "reason": f"최대 포지션 도달 ({current_count}/{RISK['max_positions']})",
            "available_cash": 0,
        }

    # 잔고 확인
    balance = broker.get_balance()
    cash = balance["cash"]
    min_order = 100_000  # 최소 주문금액 10만원

    if cash < min_order:
        return {
            "allowed": False,
            "reason": f"예수금 부족: {cash:,}원",
            "available_cash": cash,
        }

    # 일일 손실 한도 확인
    daily_pnl_pct = balance["total_pnl"] / RISK["total_capital"] * 100 if RISK["total_capital"] > 0 else 0
    if daily_pnl_pct <= -RISK["daily_loss_limit_pct"]:
        return {
            "allowed": False,
            "reason": f"일일 손실 한도 도달: {daily_pnl_pct:.1f}% (한도 -{RISK['daily_loss_limit_pct']}%)",
            "available_cash": cash,
        }

    return {
        "allowed": True,
        "reason": f"포지션 {current_count}/{RISK['max_positions']}, 예수금 {cash:,}원",
        "available_cash": cash,
    }


def check_positions_for_exit(broker):
    """
    모든 보유 포지션의 청산 조건 확인

    Returns:
        list[dict]: 청산 대상 종목 정보
    """
    from signal_generator import compute_indicators, check_sell_signal

    positions = load_positions()
    exit_candidates = []

    for ticker, pos in positions.items():
        try:
            df = broker.get_daily_ohlcv(ticker, days=50)
            if df.empty:
                continue

            df = compute_indicators(df)
            sell_signal = check_sell_signal(
                df,
                entry_date=pos["entry_date"],
                stop_loss=pos["stop_loss"]
            )

            if sell_signal["signal"]:
                exit_candidates.append({
                    "ticker": ticker,
                    "qty": pos["qty"],
                    "entry_price": pos["entry_price"],
                    "entry_date": pos["entry_date"],
                    "stop_loss": pos["stop_loss"],
                    "reason": sell_signal["reason"],
                    "exit_type": sell_signal.get("exit_type", "unknown"),
                })
        except Exception as e:
            print(f"[Risk] {ticker} 청산 확인 오류: {e}")
            continue

    return exit_candidates


def print_portfolio_status(broker):
    """포트폴리오 현황 출력"""
    balance = broker.get_balance()
    positions = load_positions()

    print(f"\n{'─'*55}")
    print(f"  포트폴리오 현황 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'─'*55}")
    print(f"  예수금:    {balance['cash']:>12,}원")
    print(f"  총평가:    {balance['total_eval']:>12,}원")
    print(f"  총손익:    {balance['total_pnl']:>12,}원")
    print(f"  보유종목:  {len(balance['positions'])}개 / {RISK['max_positions']}개")

    if balance["positions"]:
        print(f"\n  {'종목':8s} {'수량':>6s} {'평균가':>10s} {'현재가':>10s} {'손익률':>8s}")
        print(f"  {'─'*46}")
        for p in balance["positions"]:
            print(f"  {p['name'][:8]:8s} {p['qty']:>5}주 "
                  f"{p['avg_price']:>9,}원 {p['current_price']:>9,}원 "
                  f"{p['pnl_pct']:>+7.1f}%")

    if positions:
        print(f"\n  [추적 중인 포지션]")
        for ticker, pos in positions.items():
            print(f"  {ticker}: 매수일 {pos['entry_date']} | "
                  f"손절가 {pos['stop_loss']:,.0f}원")

    print(f"{'─'*55}\n")
