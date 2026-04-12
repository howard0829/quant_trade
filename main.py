"""
3일 단기매매 전략 백테스팅 파이프라인

사용법:
    python main.py                          # 기본 실행 (KOSPI 샘플 10종목)
    python main.py --market KOSPI --max 50  # KOSPI 50종목
    python main.py --market SP500 --max 30  # S&P500 30종목
    python main.py --full                   # 전체 실행 (KOSPI + KOSDAQ + SP500)
    python main.py --optimize RSI2          # RSI2 전략 파라미터 최적화
"""
import sys
import os
import argparse
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import load_market_data, get_krx_ohlcv, get_us_ohlcv
from strategies import ALL_STRATEGIES, get_strategy, list_strategies
from backtester import run_backtest, run_multi_stock_backtest, aggregate_results, results_to_dataframe
from optimizer import grid_search, multi_stock_grid_search, walk_forward_test, PARAM_GRIDS
from analyzer import full_analysis, print_analysis
from report_generator import (
    generate_strategy_report, generate_comparison_report,
    generate_optimization_report, save_report
)


def run_single_stock_test(ticker, market="KRX", start="20140101", end=None):
    """단일 종목 전체 전략 테스트"""
    print(f"\n{'='*60}")
    print(f"  단일 종목 테스트: {ticker} ({market})")
    print(f"{'='*60}")

    if market in ("KRX", "KOSPI", "KOSDAQ"):
        df = get_krx_ohlcv(ticker, start, end or datetime.now().strftime("%Y%m%d"))
    else:
        s = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        e = datetime.now().strftime("%Y-%m-%d") if not end else f"{end[:4]}-{end[4:6]}-{end[6:8]}"
        df = get_us_ohlcv(ticker, s, e)

    if df.empty:
        print(f"  데이터 없음: {ticker}")
        return

    print(f"  데이터 기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')} ({len(df)}일)")

    all_results = {}
    for name, strategy in ALL_STRATEGIES.items():
        result = run_backtest(df, strategy, ticker=ticker, market=market)
        analysis = full_analysis(result, df)
        print_analysis(analysis)
        all_results[name] = result

    return all_results


def run_market_backtest(market, max_tickers=None, start="20140101"):
    """시장 전체 백테스트"""
    print(f"\n{'#'*60}")
    print(f"  시장 백테스트: {market}")
    print(f"{'#'*60}")

    stock_data = load_market_data(market, start_date=start, max_tickers=max_tickers)
    if not stock_data:
        print("  데이터 수집 실패")
        return {}

    market_type = "US" if market == "SP500" else "KRX"
    all_agg = {}

    for name, strategy in ALL_STRATEGIES.items():
        print(f"\n--- {strategy.name} 백테스트 중 ({len(stock_data)}종목) ---")
        results = run_multi_stock_backtest(stock_data, strategy, market=market_type)
        agg = aggregate_results(results)

        if agg and agg.get("total_trades", 0) > 0:
            all_agg[name] = agg
            print(f"  거래 {agg['total_trades']}건 | 승률 {agg['win_rate']:.1f}% | "
                  f"평균수익 {agg['avg_return_pct']:.4f}% | "
                  f"PF {agg['profit_factor']:.2f}")
        else:
            print(f"  시그널 없음")

    return all_agg, stock_data


def run_optimization(market, strategy_name, max_tickers=10, start="20140101"):
    """파라미터 최적화 실행"""
    print(f"\n{'#'*60}")
    print(f"  파라미터 최적화: {strategy_name} ({market})")
    print(f"{'#'*60}")

    strategy = get_strategy(strategy_name)
    param_grid = PARAM_GRIDS.get(strategy_name)
    if not param_grid:
        print(f"  파라미터 그리드 미정의: {strategy_name}")
        return None

    stock_data = load_market_data(market, start_date=start, max_tickers=max_tickers)
    if not stock_data:
        print("  데이터 수집 실패")
        return None

    market_type = "US" if market == "SP500" else "KRX"

    print(f"  {len(stock_data)}종목 x 파라미터 조합 탐색 시작...")
    opt_results = multi_stock_grid_search(
        stock_data, strategy, param_grid,
        market=market_type, metric="win_rate", top_n=20
    )

    if not opt_results.empty:
        print(f"\n  === Top 5 파라미터 조합 ===")
        print(opt_results.head(5).to_string())

        # 리포트 저장
        report = generate_optimization_report(opt_results, strategy_name)
        save_report(report, f"optimization_{strategy_name}_{market}.md")
    else:
        print("  최적화 결과 없음")

    return opt_results


def run_walk_forward(market, strategy_name, max_tickers=5, start="20100101"):
    """Walk-Forward 검증"""
    print(f"\n--- Walk-Forward 검증: {strategy_name} ({market}) ---")

    stock_data = load_market_data(market, start_date=start, max_tickers=max_tickers)
    if not stock_data:
        return

    strategy = get_strategy(strategy_name)

    for ticker, df in list(stock_data.items())[:3]:
        print(f"\n  종목: {ticker} ({len(df)}일)")
        wf = walk_forward_test(df, strategy)

        if wf["periods"] is not None and not wf["periods"].empty:
            print(f"  검증 구간: {wf['summary']['num_periods']}개")
            print(f"  훈련 승률: {wf['summary']['avg_train_win_rate']:.1f}%")
            print(f"  검증 승률: {wf['summary']['avg_test_win_rate']:.1f}%")
            print(f"  성과 열화: {wf['summary']['avg_degradation']:.1f}%p")
            print(f"  일관성:    {'통과' if wf['summary']['consistent'] else '실패'}")
        else:
            print(f"  데이터 부족으로 Walk-Forward 불가")


def main():
    parser = argparse.ArgumentParser(description="3일 단기매매 전략 백테스팅")
    parser.add_argument("--market", default="KOSPI", choices=["KOSPI", "KOSDAQ", "SP500"],
                        help="대상 시장")
    parser.add_argument("--max", type=int, default=10, help="최대 종목 수")
    parser.add_argument("--start", default="20140101", help="시작일 (YYYYMMDD)")
    parser.add_argument("--ticker", default=None, help="단일 종목 테스트 (종목코드)")
    parser.add_argument("--optimize", default=None, help="최적화할 전략 이름")
    parser.add_argument("--walkforward", default=None, help="Walk-Forward 검증할 전략")
    parser.add_argument("--full", action="store_true", help="전체 실행 (모든 시장)")
    parser.add_argument("--list", action="store_true", help="전략 목록 출력")

    args = parser.parse_args()

    if args.list:
        print("\n사용 가능한 전략:")
        list_strategies()
        return

    # 단일 종목 테스트
    if args.ticker:
        run_single_stock_test(args.ticker, market=args.market, start=args.start)
        return

    # 파라미터 최적화
    if args.optimize:
        run_optimization(args.market, args.optimize, max_tickers=args.max, start=args.start)
        return

    # Walk-Forward 검증
    if args.walkforward:
        run_walk_forward(args.market, args.walkforward, max_tickers=args.max, start=args.start)
        return

    # 전체 실행
    if args.full:
        markets = ["KOSPI", "KOSDAQ", "SP500"]
    else:
        markets = [args.market]

    full_report_parts = []
    for market in markets:
        result = run_market_backtest(market, max_tickers=args.max, start=args.start)
        if result:
            all_agg, stock_data = result
            if all_agg:
                comparison = generate_comparison_report(all_agg, market=market)
                full_report_parts.append(comparison)
                print(f"\n{comparison}")

    # 종합 리포트 저장
    if full_report_parts:
        final_report = "\n\n---\n\n".join(full_report_parts)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        save_report(final_report, f"backtest_report_{timestamp}.md")


if __name__ == "__main__":
    main()
