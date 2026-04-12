"""
백테스트 엔진 - 전략 시그널 기반 매매 시뮬레이션

vectorbt 없이 순수 pandas로 구현하여 유연한 매매 로직 처리.
hold_days, stop_loss, target_price 등 전략별 청산 조건 지원.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class Trade:
    """개별 거래 기록"""
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp = None
    exit_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    hold_days_limit: int = 3
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """백테스트 결과"""
    strategy_name: str
    ticker: str
    trades: list = field(default_factory=list)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


def run_backtest(df, strategy, ticker="UNKNOWN", commission=0.00015,
                 slippage=0.001, tax=0.0018, market="KRX", **strategy_params):
    """
    단일 종목 백테스트 실행

    Parameters:
        df: OHLCV DataFrame
        strategy: BaseStrategy 인스턴스
        ticker: 종목 코드
        commission: 수수료 (편도)
        slippage: 슬리피지
        tax: 매도 시 세금 (한국: 0.18%)
        market: "KRX" 또는 "US"
        **strategy_params: 전략 파라미터 오버라이드

    Returns:
        BacktestResult
    """
    # 비용 설정
    if market == "US":
        commission = 0.0
        tax = 0.0
        slippage = 0.001

    # 시그널 생성
    sig_df = strategy.generate_signals(df, **strategy_params)

    trades = []
    position = None  # 현재 보유 포지션

    for i in range(1, len(sig_df)):
        row = sig_df.iloc[i]
        prev_row = sig_df.iloc[i - 1]
        date = sig_df.index[i]

        # 포지션 보유 중이면 청산 조건 확인
        if position is not None:
            days_held = (date - position.entry_date).days
            trade_days_held = sum(1 for d in sig_df.index
                                 if position.entry_date < d <= date)

            # 청산 조건 1: 손절
            if position.stop_loss > 0 and row["Low"] <= position.stop_loss:
                position.exit_date = date
                position.exit_price = position.stop_loss
                position.exit_reason = "stop_loss"
                _finalize_trade(position, commission, slippage, tax)
                trades.append(position)
                position = None
                continue

            # 청산 조건 2: 목표가 도달
            if hasattr(row, "target_price") and "target_price" in sig_df.columns:
                tp = sig_df.loc[position.entry_date, "target_price"] if position.entry_date in sig_df.index else 0
                if tp > 0 and row["High"] >= tp:
                    position.exit_date = date
                    position.exit_price = tp
                    position.exit_reason = "target"
                    _finalize_trade(position, commission, slippage, tax)
                    trades.append(position)
                    position = None
                    continue

            # 청산 조건 3: 매도 시그널
            if "exit" in sig_df.columns and row.get("exit", 0) == 1:
                position.exit_date = date
                position.exit_price = row["Close"]
                position.exit_reason = "signal"
                _finalize_trade(position, commission, slippage, tax)
                trades.append(position)
                position = None
                continue

            # 청산 조건 4: 보유기간 초과
            hold_limit = sig_df.loc[position.entry_date, "hold_days"] if "hold_days" in sig_df.columns else 3
            if trade_days_held >= hold_limit:
                position.exit_date = date
                position.exit_price = row["Close"]
                position.exit_reason = "time"
                _finalize_trade(position, commission, slippage, tax)
                trades.append(position)
                position = None
                continue

        # 진입 조건 확인 (포지션 없을 때만)
        if position is None and row.get("entry", 0) == 1:
            stop = row.get("stop_loss", 0)
            target = row.get("target_price", 0)
            hold = row.get("hold_days", 3)

            position = Trade(
                ticker=ticker,
                entry_date=date,
                entry_price=row["Close"] * (1 + slippage),  # 슬리피지 반영
                stop_loss=stop,
                target_price=target,
                hold_days_limit=hold if isinstance(hold, (int, float)) else 3,
            )

    # 마지막 미청산 포지션 처리
    if position is not None:
        position.exit_date = sig_df.index[-1]
        position.exit_price = sig_df.iloc[-1]["Close"]
        position.exit_reason = "end"
        _finalize_trade(position, commission, slippage, tax)
        trades.append(position)

    return _compile_result(strategy.name, ticker, trades)


def _finalize_trade(trade, commission, slippage, tax):
    """거래 손익 계산 (비용 포함)"""
    entry_cost = trade.entry_price * commission
    exit_cost = trade.exit_price * (commission + tax) + trade.exit_price * slippage
    trade.pnl = trade.exit_price - trade.entry_price - entry_cost - exit_cost
    trade.pnl_pct = trade.pnl / trade.entry_price * 100


def _compile_result(strategy_name, ticker, trades):
    """거래 목록에서 성과 지표 계산"""
    result = BacktestResult(strategy_name=strategy_name, ticker=ticker, trades=trades)
    result.total_trades = len(trades)

    if not trades:
        return result

    returns = [t.pnl_pct for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    result.winning_trades = len(wins)
    result.losing_trades = len(losses)
    result.win_rate = len(wins) / len(returns) * 100 if returns else 0
    result.avg_return = np.mean(returns) if returns else 0
    result.avg_win = np.mean(wins) if wins else 0
    result.avg_loss = np.mean(losses) if losses else 0

    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0
    result.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")
    result.total_return = sum(returns)

    # MDD 계산
    if returns:
        cum = np.cumsum(returns)
        peak = np.maximum.accumulate(cum)
        dd = cum - peak
        result.max_drawdown = abs(np.min(dd)) if len(dd) > 0 else 0

    # Sharpe Ratio (일간 수익률 기준, 연환산)
    if len(returns) > 1:
        result.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

    return result


def run_multi_stock_backtest(stock_data, strategy, market="KRX", **strategy_params):
    """
    다수 종목 백테스트 실행

    Parameters:
        stock_data: dict[str, pd.DataFrame] - {ticker: OHLCV DataFrame}
        strategy: BaseStrategy 인스턴스
        market: "KRX" 또는 "US"

    Returns:
        list[BacktestResult]
    """
    results = []
    total = len(stock_data)
    for i, (ticker, df) in enumerate(stock_data.items()):
        try:
            result = run_backtest(df, strategy, ticker=ticker, market=market, **strategy_params)
            if result.total_trades > 0:
                results.append(result)
        except Exception as e:
            print(f"  [{i+1}/{total}] {ticker} 백테스트 실패: {e}")
            continue
    return results


def aggregate_results(results):
    """다수 종목 결과를 집계"""
    if not results:
        return {}

    all_trades = []
    for r in results:
        all_trades.extend(r.trades)

    if not all_trades:
        return {"total_trades": 0}

    returns = [t.pnl_pct for t in all_trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0

    return {
        "total_stocks": len(results),
        "total_trades": len(all_trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(returns) * 100,
        "avg_return_pct": np.mean(returns),
        "avg_win_pct": np.mean(wins) if wins else 0,
        "avg_loss_pct": np.mean(losses) if losses else 0,
        "profit_factor": total_wins / total_losses if total_losses > 0 else float("inf"),
        "total_return_pct": sum(returns),
        "sharpe_ratio": np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0,
        "median_return_pct": np.median(returns),
    }


def results_to_dataframe(results):
    """BacktestResult 리스트를 DataFrame으로 변환"""
    rows = []
    for r in results:
        rows.append({
            "ticker": r.ticker,
            "total_trades": r.total_trades,
            "win_rate": round(r.win_rate, 2),
            "avg_return": round(r.avg_return, 4),
            "avg_win": round(r.avg_win, 4),
            "avg_loss": round(r.avg_loss, 4),
            "profit_factor": round(r.profit_factor, 2),
            "total_return": round(r.total_return, 2),
            "max_drawdown": round(r.max_drawdown, 2),
            "sharpe_ratio": round(r.sharpe_ratio, 2),
        })
    return pd.DataFrame(rows)
