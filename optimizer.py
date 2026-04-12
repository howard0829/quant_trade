"""
파라미터 최적화 모듈 - 그리드 서치 및 Walk-Forward 검증
"""
import itertools
import pandas as pd
import numpy as np
from backtester import run_backtest, aggregate_results


def grid_search(df, strategy, param_grid, ticker="TEST", market="KRX", metric="win_rate"):
    """
    파라미터 그리드 서치

    Parameters:
        df: OHLCV DataFrame
        strategy: BaseStrategy 인스턴스
        param_grid: dict[str, list] - 탐색할 파라미터 그리드
            예: {"rsi_period": [2, 3, 5], "rsi_threshold": [5, 10, 15]}
        ticker: 종목 코드
        market: "KRX" 또는 "US"
        metric: 최적화 기준 ("win_rate", "avg_return", "profit_factor", "sharpe_ratio")

    Returns:
        pd.DataFrame: 파라미터 조합별 성과
    """
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(itertools.product(*values))

    results = []
    total = len(combos)

    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        try:
            result = run_backtest(df, strategy, ticker=ticker, market=market, **params)
            row = {
                **params,
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "avg_return": result.avg_return,
                "avg_win": result.avg_win,
                "avg_loss": result.avg_loss,
                "profit_factor": result.profit_factor,
                "total_return": result.total_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
            }
            results.append(row)
        except Exception as e:
            continue

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{total}] 파라미터 조합 탐색 중...")

    if not results:
        return pd.DataFrame()

    df_results = pd.DataFrame(results)
    # 최소 거래 횟수 필터 (30회 미만은 신뢰도 낮음)
    df_results = df_results[df_results["total_trades"] >= 10]
    df_results = df_results.sort_values(metric, ascending=False).reset_index(drop=True)
    return df_results


def multi_stock_grid_search(stock_data, strategy, param_grid, market="KRX",
                            metric="win_rate", top_n=10):
    """
    다수 종목에 대한 그리드 서치 (종목 평균 성과 기준)

    Parameters:
        stock_data: dict[str, pd.DataFrame]
        strategy: BaseStrategy 인스턴스
        param_grid: dict[str, list]
        market: 시장
        metric: 최적화 기준
        top_n: 상위 N개 결과 반환

    Returns:
        pd.DataFrame: 파라미터 조합별 종목 평균 성과
    """
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(itertools.product(*values))

    agg_results = []
    total = len(combos)
    tickers = list(stock_data.keys())

    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        combo_returns = []
        combo_wins = 0
        combo_total = 0

        for ticker in tickers:
            try:
                result = run_backtest(stock_data[ticker], strategy,
                                      ticker=ticker, market=market, **params)
                if result.total_trades > 0:
                    combo_returns.extend([t.pnl_pct for t in result.trades])
                    combo_wins += result.winning_trades
                    combo_total += result.total_trades
            except Exception:
                continue

        if combo_total >= 10:
            wins = [r for r in combo_returns if r > 0]
            losses = [r for r in combo_returns if r <= 0]
            total_wins_val = sum(wins) if wins else 0
            total_losses_val = abs(sum(losses)) if losses else 0

            row = {
                **params,
                "total_trades": combo_total,
                "win_rate": combo_wins / combo_total * 100,
                "avg_return": np.mean(combo_returns),
                "profit_factor": total_wins_val / total_losses_val if total_losses_val > 0 else float("inf"),
                "sharpe_ratio": np.mean(combo_returns) / np.std(combo_returns) * np.sqrt(252) if np.std(combo_returns) > 0 else 0,
                "num_stocks": len(set(t for t in tickers if t in stock_data)),
            }
            agg_results.append(row)

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{total}] 파라미터 조합 탐색 중...")

    if not agg_results:
        return pd.DataFrame()

    df_results = pd.DataFrame(agg_results)
    df_results = df_results.sort_values(metric, ascending=False).head(top_n).reset_index(drop=True)
    return df_results


def walk_forward_test(df, strategy, train_years=5, test_years=2, **strategy_params):
    """
    Walk-Forward Analysis (과적합 방지)

    데이터를 train_years + test_years 윈도우로 롤링하며
    훈련 구간 최적 파라미터를 검증 구간에서 테스트.

    Parameters:
        df: OHLCV DataFrame (최소 train_years + test_years 이상)
        strategy: BaseStrategy 인스턴스
        train_years: 훈련 기간 (년)
        test_years: 검증 기간 (년)

    Returns:
        dict: 구간별 성과 요약
    """
    results = []
    dates = df.index
    start = dates[0]
    end = dates[-1]
    total_days = (end - start).days

    train_days = train_years * 252  # 영업일 기준
    test_days = test_years * 252
    step_days = test_days  # 비중복 롤링

    i = 0
    while i + train_days + test_days <= len(df):
        train_df = df.iloc[i:i + train_days]
        test_df = df.iloc[i + train_days:i + train_days + test_days]

        if len(test_df) < 50:
            break

        # 훈련 구간 백테스트
        train_result = run_backtest(train_df, strategy, ticker="TRAIN", **strategy_params)

        # 검증 구간 백테스트 (동일 파라미터)
        test_result = run_backtest(test_df, strategy, ticker="TEST", **strategy_params)

        results.append({
            "period": f"{train_df.index[0].strftime('%Y%m%d')}-{test_df.index[-1].strftime('%Y%m%d')}",
            "train_start": train_df.index[0],
            "train_end": train_df.index[-1],
            "test_start": test_df.index[0],
            "test_end": test_df.index[-1],
            "train_trades": train_result.total_trades,
            "train_win_rate": train_result.win_rate,
            "train_avg_return": train_result.avg_return,
            "test_trades": test_result.total_trades,
            "test_win_rate": test_result.win_rate,
            "test_avg_return": test_result.avg_return,
            "test_profit_factor": test_result.profit_factor,
            "degradation": train_result.win_rate - test_result.win_rate,
        })

        i += step_days

    if not results:
        return {"periods": [], "summary": {}}

    df_wf = pd.DataFrame(results)
    summary = {
        "num_periods": len(results),
        "avg_train_win_rate": df_wf["train_win_rate"].mean(),
        "avg_test_win_rate": df_wf["test_win_rate"].mean(),
        "avg_degradation": df_wf["degradation"].mean(),
        "worst_test_win_rate": df_wf["test_win_rate"].min(),
        "consistent": df_wf["degradation"].mean() < 10,  # 열화 10%p 미만이면 일관적
    }

    return {"periods": df_wf, "summary": summary}


# 전략별 기본 파라미터 그리드
PARAM_GRIDS = {
    "RSI2": {
        "rsi_period": [2, 3, 5],
        "rsi_threshold": [5, 10, 15, 20],
        "trend_period": [50, 100, 200],
        "exit_period": [3, 5, 7],
    },
    "VCP": {
        "range_threshold": [0.4, 0.5, 0.6, 0.7],
        "vol_threshold": [1.5, 2.0, 2.5, 3.0],
        "hold_days": [2, 3, 5],
    },
    "GapDown": {
        "gap_min": [-3.0, -2.0, -1.5],
        "gap_max": [-0.3, -0.5, -1.0],
        "hold_days": [1, 2, 3],
        "stop_pct": [1.0, 1.5, 2.0],
    },
    "VolSpike_RSI": {
        "rsi_period": [7, 14],
        "rsi_threshold": [20, 25, 30, 35],
        "vol_mult": [2.0, 3.0, 5.0],
        "hold_days": [2, 3, 5],
    },
    "VWAP": {
        "vol_mult": [1.0, 1.5, 2.0, 2.5],
        "hold_days": [2, 3, 5],
    },
    "OBV_Div": {
        "lookback": [10, 15, 20, 30],
        "hold_days": [2, 3, 5],
        "atr_mult": [1.5, 2.0, 2.5],
    },
}
