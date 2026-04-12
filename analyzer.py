"""
성과 분석 모듈 - 백테스트 결과 심층 분석
"""
import pandas as pd
import numpy as np
from backtester import BacktestResult


def analyze_by_year(trades):
    """연도별 성과 분석"""
    if not trades:
        return pd.DataFrame()

    rows = []
    for t in trades:
        rows.append({
            "year": t.entry_date.year,
            "pnl_pct": t.pnl_pct,
            "win": 1 if t.pnl_pct > 0 else 0,
            "exit_reason": t.exit_reason,
        })

    df = pd.DataFrame(rows)
    yearly = df.groupby("year").agg(
        trades=("pnl_pct", "count"),
        win_rate=("win", "mean"),
        avg_return=("pnl_pct", "mean"),
        total_return=("pnl_pct", "sum"),
        median_return=("pnl_pct", "median"),
        best_trade=("pnl_pct", "max"),
        worst_trade=("pnl_pct", "min"),
    ).reset_index()

    yearly["win_rate"] = (yearly["win_rate"] * 100).round(2)
    yearly["avg_return"] = yearly["avg_return"].round(4)
    yearly["total_return"] = yearly["total_return"].round(2)
    return yearly


def analyze_by_exit_reason(trades):
    """청산 사유별 분석"""
    if not trades:
        return pd.DataFrame()

    rows = [{"exit_reason": t.exit_reason, "pnl_pct": t.pnl_pct} for t in trades]
    df = pd.DataFrame(rows)

    return df.groupby("exit_reason").agg(
        count=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_return=("pnl_pct", "mean"),
        total_return=("pnl_pct", "sum"),
    ).round(4).reset_index()


def analyze_market_regime(df, trades, sma_period=200):
    """
    시장 환경별 성과 분석
    - 상승장: 종가 > SMA(200)
    - 하락장: 종가 < SMA(200)
    """
    if not trades:
        return {}

    sma_values = df["Close"].rolling(window=sma_period, min_periods=sma_period).mean()

    bull_trades = []
    bear_trades = []

    for t in trades:
        if t.entry_date in df.index:
            idx = df.index.get_loc(t.entry_date)
            if idx < len(sma_values) and pd.notna(sma_values.iloc[idx]):
                if df["Close"].iloc[idx] > sma_values.iloc[idx]:
                    bull_trades.append(t.pnl_pct)
                else:
                    bear_trades.append(t.pnl_pct)

    result = {}
    if bull_trades:
        bull_wins = [r for r in bull_trades if r > 0]
        result["bull_market"] = {
            "trades": len(bull_trades),
            "win_rate": len(bull_wins) / len(bull_trades) * 100,
            "avg_return": np.mean(bull_trades),
        }
    if bear_trades:
        bear_wins = [r for r in bear_trades if r > 0]
        result["bear_market"] = {
            "trades": len(bear_trades),
            "win_rate": len(bear_wins) / len(bear_trades) * 100,
            "avg_return": np.mean(bear_trades),
        }
    return result


def analyze_holding_period(trades):
    """보유기간별 성과 분석"""
    if not trades:
        return pd.DataFrame()

    rows = []
    for t in trades:
        if t.entry_date and t.exit_date:
            # 영업일 기준 보유기간
            hold_days = np.busday_count(
                t.entry_date.date(), t.exit_date.date()
            )
            rows.append({"hold_days": hold_days, "pnl_pct": t.pnl_pct})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df.groupby("hold_days").agg(
        count=("pnl_pct", "count"),
        win_rate=("pnl_pct", lambda x: (x > 0).mean() * 100),
        avg_return=("pnl_pct", "mean"),
    ).round(4).reset_index()


def full_analysis(result, df=None):
    """
    종합 분석 실행

    Parameters:
        result: BacktestResult
        df: 원본 OHLCV DataFrame (시장환경 분석용)

    Returns:
        dict: 분석 결과 딕셔너리
    """
    analysis = {
        "summary": {
            "strategy": result.strategy_name,
            "ticker": result.ticker,
            "total_trades": result.total_trades,
            "win_rate": round(result.win_rate, 2),
            "avg_return": round(result.avg_return, 4),
            "avg_win": round(result.avg_win, 4),
            "avg_loss": round(result.avg_loss, 4),
            "profit_factor": round(result.profit_factor, 2),
            "total_return": round(result.total_return, 2),
            "max_drawdown": round(result.max_drawdown, 2),
            "sharpe_ratio": round(result.sharpe_ratio, 2),
        },
        "by_year": analyze_by_year(result.trades),
        "by_exit_reason": analyze_by_exit_reason(result.trades),
        "by_holding_period": analyze_holding_period(result.trades),
    }

    if df is not None:
        analysis["by_market_regime"] = analyze_market_regime(df, result.trades)

    return analysis


def print_analysis(analysis):
    """분석 결과 출력"""
    s = analysis["summary"]
    print(f"\n{'='*60}")
    print(f"  전략: {s['strategy']}  |  종목: {s['ticker']}")
    print(f"{'='*60}")
    print(f"  총 거래 수:    {s['total_trades']}")
    print(f"  승률:          {s['win_rate']}%")
    print(f"  평균 수익률:   {s['avg_return']}%")
    print(f"  평균 이익:     {s['avg_win']}%")
    print(f"  평균 손실:     {s['avg_loss']}%")
    print(f"  Profit Factor: {s['profit_factor']}")
    print(f"  총 수익률:     {s['total_return']}%")
    print(f"  MDD:           {s['max_drawdown']}%")
    print(f"  Sharpe Ratio:  {s['sharpe_ratio']}")

    if not analysis["by_year"].empty:
        print(f"\n--- 연도별 성과 ---")
        print(analysis["by_year"].to_string(index=False))

    if not analysis["by_exit_reason"].empty:
        print(f"\n--- 청산 사유별 ---")
        print(analysis["by_exit_reason"].to_string(index=False))

    if "by_market_regime" in analysis and analysis["by_market_regime"]:
        print(f"\n--- 시장 환경별 ---")
        for regime, data in analysis["by_market_regime"].items():
            label = "상승장" if regime == "bull_market" else "하락장"
            print(f"  {label}: 거래 {data['trades']}건, 승률 {data['win_rate']:.1f}%, 평균수익 {data['avg_return']:.4f}%")

    print(f"{'='*60}\n")
