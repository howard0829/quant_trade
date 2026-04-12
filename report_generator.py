"""
결과 리포트 생성 모듈 - Markdown 형식 리포트 출력
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from analyzer import full_analysis, analyze_by_year


def generate_strategy_report(result, df=None, strategy_params=None):
    """단일 전략-종목 리포트 생성"""
    analysis = full_analysis(result, df)
    s = analysis["summary"]

    report = []
    report.append(f"## {s['strategy']} - {s['ticker']}")
    report.append("")

    # 요약
    report.append("### 성과 요약")
    report.append(f"| 지표 | 값 |")
    report.append(f"|------|-----|")
    report.append(f"| 총 거래 수 | {s['total_trades']} |")
    report.append(f"| 승률 | {s['win_rate']}% |")
    report.append(f"| 평균 수익률 | {s['avg_return']}% |")
    report.append(f"| 평균 이익 | {s['avg_win']}% |")
    report.append(f"| 평균 손실 | {s['avg_loss']}% |")
    report.append(f"| Profit Factor | {s['profit_factor']} |")
    report.append(f"| 총 수익률 | {s['total_return']}% |")
    report.append(f"| MDD | {s['max_drawdown']}% |")
    report.append(f"| Sharpe Ratio | {s['sharpe_ratio']} |")
    report.append("")

    # 파라미터
    if strategy_params:
        report.append("### 사용 파라미터")
        for k, v in strategy_params.items():
            report.append(f"- **{k}**: {v}")
        report.append("")

    # 연도별
    yearly = analysis["by_year"]
    if not yearly.empty:
        report.append("### 연도별 성과")
        report.append(yearly.to_markdown(index=False))
        report.append("")

    # 청산 사유별
    exit_df = analysis["by_exit_reason"]
    if not exit_df.empty:
        report.append("### 청산 사유별 성과")
        report.append(exit_df.to_markdown(index=False))
        report.append("")

    # 시장 환경별
    if "by_market_regime" in analysis and analysis["by_market_regime"]:
        report.append("### 시장 환경별 성과")
        report.append("| 환경 | 거래 수 | 승률 | 평균 수익률 |")
        report.append("|------|---------|------|-----------|")
        for regime, data in analysis["by_market_regime"].items():
            label = "상승장" if regime == "bull_market" else "하락장"
            report.append(f"| {label} | {data['trades']} | {data['win_rate']:.1f}% | {data['avg_return']:.4f}% |")
        report.append("")

    return "\n".join(report)


def generate_comparison_report(all_results, market="KRX"):
    """
    전략 간 비교 리포트

    Parameters:
        all_results: dict[str, dict] - {strategy_name: aggregate_results}
        market: 시장명

    Returns:
        str: Markdown 리포트
    """
    report = []
    report.append(f"# 3일 단기매매 전략 비교 리포트")
    report.append(f"")
    report.append(f"- **시장**: {market}")
    report.append(f"- **생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"")

    # 비교 테이블
    report.append("## 전략 성과 비교")
    report.append("")
    report.append("| 전략 | 거래 수 | 승률 | 평균수익 | Profit Factor | Sharpe |")
    report.append("|------|---------|------|---------|--------------|--------|")

    ranked = []
    for name, agg in all_results.items():
        if not agg or agg.get("total_trades", 0) == 0:
            continue
        row = {
            "name": name,
            "trades": agg["total_trades"],
            "win_rate": agg["win_rate"],
            "avg_return": agg["avg_return_pct"],
            "profit_factor": agg["profit_factor"],
            "sharpe": agg.get("sharpe_ratio", 0),
        }
        ranked.append(row)
        pf = f"{row['profit_factor']:.2f}" if row["profit_factor"] != float("inf") else "∞"
        report.append(
            f"| {name} | {row['trades']} | {row['win_rate']:.1f}% | "
            f"{row['avg_return']:.4f}% | {pf} | {row['sharpe']:.2f} |"
        )

    report.append("")

    # 종합 순위
    if ranked:
        # 복합 점수 = 승률*0.3 + (profit_factor 정규화)*0.3 + (sharpe 정규화)*0.4
        for r in ranked:
            pf = min(r["profit_factor"], 10)  # inf 방지
            r["score"] = r["win_rate"] * 0.3 + pf * 10 * 0.3 + max(r["sharpe"], 0) * 10 * 0.4

        ranked.sort(key=lambda x: x["score"], reverse=True)

        report.append("## 종합 순위")
        report.append("")
        for i, r in enumerate(ranked):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            report.append(f"{medal} **{r['name']}** - 승률 {r['win_rate']:.1f}%, "
                         f"평균수익 {r['avg_return']:.4f}%, Sharpe {r['sharpe']:.2f}")
        report.append("")

    return "\n".join(report)


def generate_optimization_report(opt_results, strategy_name):
    """파라미터 최적화 결과 리포트"""
    report = []
    report.append(f"## {strategy_name} 파라미터 최적화 결과")
    report.append("")

    if opt_results.empty:
        report.append("최적화 결과 없음 (최소 거래 횟수 미달)")
        return "\n".join(report)

    report.append(f"### Top 10 파라미터 조합")
    report.append("")
    report.append(opt_results.head(10).to_markdown(index=False))
    report.append("")

    # 최적 파라미터
    best = opt_results.iloc[0]
    report.append(f"### 최적 파라미터")
    report.append("")
    param_cols = [c for c in opt_results.columns
                  if c not in ["total_trades", "win_rate", "avg_return", "avg_win",
                               "avg_loss", "profit_factor", "total_return",
                               "max_drawdown", "sharpe_ratio", "num_stocks"]]
    for col in param_cols:
        report.append(f"- **{col}**: {best[col]}")
    report.append("")
    report.append(f"- 승률: {best['win_rate']:.1f}%")
    report.append(f"- 평균수익: {best['avg_return']:.4f}%")
    report.append(f"- 거래 수: {int(best['total_trades'])}")

    return "\n".join(report)


def save_report(content, filename, output_dir="/Users/howard/Project/stock_strategy/reports"):
    """리포트를 파일로 저장"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"리포트 저장: {filepath}")
    return filepath
