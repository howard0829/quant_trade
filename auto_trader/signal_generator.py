"""
매매 시그널 생성 모듈 - RSI(5) 평균회귀 전략

백테스트 결과 확인된 최적 조건:
  매수: RSI(5) < 10 AND 종가 > SMA(100)
  매도: 종가 > SMA(3)
  손절: ATR(14) × 2.5 하방
"""
import pandas as pd
import numpy as np
from config import STRATEGY


def rsi(close, period):
    """RSI 계산"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def sma(series, period):
    """단순 이동평균"""
    return series.rolling(window=period, min_periods=period).mean()


def atr(high, low, close, period):
    """ATR (Average True Range)"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def compute_indicators(df):
    """
    OHLCV DataFrame에 전략 지표를 추가

    Parameters:
        df: OHLCV DataFrame (Open, High, Low, Close, Volume)

    Returns:
        DataFrame with indicator columns added
    """
    p = STRATEGY
    df = df.copy()

    df["RSI"] = rsi(df["Close"], p["rsi_period"])
    df["SMA_TREND"] = sma(df["Close"], p["trend_sma_period"])
    df["SMA_EXIT"] = sma(df["Close"], p["exit_sma_period"])
    df["ATR"] = atr(df["High"], df["Low"], df["Close"], p["atr_period"])

    return df


def check_buy_signal(df):
    """
    매수 시그널 확인

    Parameters:
        df: 지표가 계산된 DataFrame

    Returns:
        dict: {"signal": bool, "price": float, "stop_loss": float,
               "rsi": float, "sma_trend": float, "atr": float}
    """
    if len(df) < STRATEGY["trend_sma_period"]:
        return {"signal": False, "reason": "데이터 부족"}

    last = df.iloc[-1]

    # 지표값 유효성 확인
    if pd.isna(last["RSI"]) or pd.isna(last["SMA_TREND"]) or pd.isna(last["ATR"]):
        return {"signal": False, "reason": "지표 계산 불가"}

    rsi_val = last["RSI"]
    close = last["Close"]
    sma_trend = last["SMA_TREND"]
    atr_val = last["ATR"]

    # 매수 조건: RSI(5) < 10 AND 종가 > SMA(100)
    buy_signal = (rsi_val < STRATEGY["rsi_threshold"]) and (close > sma_trend)

    stop_loss = close - atr_val * STRATEGY["atr_stop_mult"]

    return {
        "signal": buy_signal,
        "price": close,
        "stop_loss": stop_loss,
        "rsi": round(rsi_val, 2),
        "sma_trend": round(sma_trend, 2),
        "atr": round(atr_val, 2),
        "reason": f"RSI={rsi_val:.1f}, Close={close:,}, SMA100={sma_trend:,.0f}"
    }


def check_sell_signal(df, entry_date=None, stop_loss=0):
    """
    매도 시그널 확인

    Parameters:
        df: 지표가 계산된 DataFrame
        entry_date: 매수일 (보유기간 체크용)
        stop_loss: 손절가

    Returns:
        dict: {"signal": bool, "reason": str}
    """
    if len(df) < 5:
        return {"signal": False, "reason": "데이터 부족"}

    last = df.iloc[-1]
    close = last["Close"]
    low = last["Low"]
    sma_exit = last["SMA_EXIT"]

    # 청산 조건 1: 종가 > SMA(3) → 시그널 매도
    if not pd.isna(sma_exit) and close > sma_exit:
        return {
            "signal": True,
            "reason": f"시그널 매도: Close={close:,} > SMA3={sma_exit:,.0f}",
            "exit_type": "signal",
        }

    # 청산 조건 2: 손절가 이탈
    if stop_loss > 0 and low <= stop_loss:
        return {
            "signal": True,
            "reason": f"손절: Low={low:,} <= StopLoss={stop_loss:,.0f}",
            "exit_type": "stop_loss",
        }

    # 청산 조건 3: 최대 보유기간 초과
    if entry_date:
        today = df.index[-1]
        hold_days = np.busday_count(
            pd.Timestamp(entry_date).date(),
            pd.Timestamp(today).date()
        )
        if hold_days >= STRATEGY["max_hold_days"]:
            return {
                "signal": True,
                "reason": f"보유기간 만료: {hold_days}일 >= {STRATEGY['max_hold_days']}일",
                "exit_type": "time",
            }

    return {
        "signal": False,
        "reason": f"홀드: Close={close:,}, SMA3={sma_exit:,.0f}" if not pd.isna(sma_exit) else "홀드",
        "exit_type": None,
    }


def scan_universe(broker, tickers):
    """
    전체 종목 스캔하여 매수 시그널 발생 종목 리스트 반환

    Parameters:
        broker: Broker 인스턴스
        tickers: 종목코드 리스트

    Returns:
        list[dict]: 매수 시그널 발생 종목 정보
    """
    buy_candidates = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        try:
            df = broker.get_daily_ohlcv(ticker, days=200)
            if df.empty or len(df) < STRATEGY["trend_sma_period"]:
                continue

            df = compute_indicators(df)
            signal = check_buy_signal(df)

            if signal["signal"]:
                signal["ticker"] = ticker
                buy_candidates.append(signal)
                print(f"  [매수시그널] {ticker}: {signal['reason']}")

        except Exception as e:
            continue

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{total}] 스캔 진행 중...")

    print(f"  스캔 완료: {len(buy_candidates)}개 매수 시그널 발견 / {total}종목")
    return buy_candidates
