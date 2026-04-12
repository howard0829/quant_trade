"""
기술적 지표 계산 모듈 - RSI, OBV, RVOL, VWAP, ATR, SMA 등
"""
import pandas as pd
import numpy as np


def sma(series, period):
    """단순 이동평균"""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series, period):
    """지수 이동평균"""
    return series.ewm(span=period, adjust=False).mean()


def rsi(close, period=14):
    """RSI (Relative Strength Index)"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(high, low, close, period=14):
    """ATR (Average True Range)"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=period, min_periods=period).mean()


def obv(close, volume):
    """OBV (On-Balance Volume)"""
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (volume * direction).cumsum()


def rvol(volume, period=20):
    """RVOL (Relative Volume) - 현재 거래량 / 평균 거래량"""
    avg_vol = volume.rolling(window=period, min_periods=period).mean()
    return volume / avg_vol


def vwap_daily(high, low, close, volume):
    """
    일봉 기준 VWAP 근사 (일중 데이터 없이 Typical Price * Volume 누적)
    실제로는 일봉에서는 누적 VWAP를 rolling으로 계산
    """
    typical_price = (high + low + close) / 3
    cumulative_tp_vol = (typical_price * volume).rolling(window=20, min_periods=1).sum()
    cumulative_vol = volume.rolling(window=20, min_periods=1).sum()
    return cumulative_tp_vol / cumulative_vol


def volume_spike(volume, period=20, threshold=3.0):
    """거래량 급증 시그널 (평균 대비 threshold배 이상)"""
    avg_vol = volume.rolling(window=period, min_periods=period).mean()
    return volume > (avg_vol * threshold)


def price_range_ratio(high, low, close, period=20):
    """가격 레인지 축소 비율 (현재 레인지 / 과거 평균 레인지)"""
    daily_range = high - low
    avg_range = daily_range.rolling(window=period, min_periods=period).mean()
    current_range = daily_range.rolling(window=5, min_periods=5).mean()
    return current_range / avg_range


def gap_percentage(open_price, prev_close):
    """갭 비율 계산"""
    return (open_price - prev_close) / prev_close * 100


def obv_divergence(close, volume, lookback=20):
    """
    OBV 다이버전스 감지
    주가 저점 갱신 BUT OBV 저점 미갱신 = 상승 다이버전스 (True)
    """
    obv_values = obv(close, volume)

    # 최근 lookback 기간 내 최저가 vs 이전 lookback 기간 내 최저가
    price_min_recent = close.rolling(window=lookback, min_periods=lookback).min()
    price_min_prev = close.shift(lookback).rolling(window=lookback, min_periods=lookback).min()

    obv_min_recent = obv_values.rolling(window=lookback, min_periods=lookback).min()
    obv_min_prev = obv_values.shift(lookback).rolling(window=lookback, min_periods=lookback).min()

    # 주가는 새 저점, OBV는 새 저점 아님
    bullish_div = (price_min_recent < price_min_prev) & (obv_min_recent > obv_min_prev)
    return bullish_div


def add_all_indicators(df):
    """DataFrame에 모든 기술적 지표를 추가"""
    df = df.copy()

    # 이동평균
    df["SMA_5"] = sma(df["Close"], 5)
    df["SMA_20"] = sma(df["Close"], 20)
    df["SMA_50"] = sma(df["Close"], 50)
    df["SMA_200"] = sma(df["Close"], 200)

    # RSI
    df["RSI_2"] = rsi(df["Close"], 2)
    df["RSI_14"] = rsi(df["Close"], 14)

    # ATR
    df["ATR_14"] = atr(df["High"], df["Low"], df["Close"], 14)

    # 거래량 관련
    df["OBV"] = obv(df["Close"], df["Volume"])
    df["RVOL"] = rvol(df["Volume"], 20)
    df["Vol_Spike"] = volume_spike(df["Volume"], 20, 3.0)

    # VWAP
    df["VWAP"] = vwap_daily(df["High"], df["Low"], df["Close"], df["Volume"])

    # 가격 레인지
    df["Range_Ratio"] = price_range_ratio(df["High"], df["Low"], df["Close"], 20)

    # 갭
    df["Gap_Pct"] = gap_percentage(df["Open"], df["Close"].shift(1))

    # OBV 다이버전스
    df["OBV_Bullish_Div"] = obv_divergence(df["Close"], df["Volume"], 20)

    return df


if __name__ == "__main__":
    # 테스트
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=300, freq="B")
    test_df = pd.DataFrame({
        "Open": np.random.uniform(100, 110, 300),
        "High": np.random.uniform(110, 120, 300),
        "Low": np.random.uniform(90, 100, 300),
        "Close": np.random.uniform(100, 110, 300),
        "Volume": np.random.randint(1000000, 5000000, 300),
    }, index=dates)

    result = add_all_indicators(test_df)
    print("지표 계산 완료:")
    print(result.columns.tolist())
    print(result[["RSI_2", "RSI_14", "ATR_14", "RVOL", "VWAP"]].tail())
