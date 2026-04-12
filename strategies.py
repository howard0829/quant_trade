"""
6개 단기매매 전략 시그널 생성 모듈

각 전략은 DataFrame을 입력받아 매수/매도 시그널 컬럼을 추가하여 반환한다.
시그널: 1 = 매수, -1 = 매도, 0 = 홀드
"""
import pandas as pd
import numpy as np
from indicators import add_all_indicators, rsi, sma, atr, rvol, obv, volume_spike, vwap_daily


class BaseStrategy:
    """전략 기본 클래스"""
    name = "Base"
    description = ""

    def generate_signals(self, df, **params):
        raise NotImplementedError

    def get_default_params(self):
        raise NotImplementedError


class RSI2MeanReversion(BaseStrategy):
    """
    전략 1: Connors RSI(2) 평균회귀
    - 매수: RSI(2) < threshold AND 종가 > SMA(trend_period)
    - 매도: 종가 > SMA(exit_period)
    - 손절: ATR(14) x atr_mult 하방
    """
    name = "RSI2_MeanReversion"
    description = "RSI(2) 과매도 진입 → SMA(5) 상향 돌파 시 청산"

    def get_default_params(self):
        return {
            "rsi_period": 2,
            "rsi_threshold": 5,
            "trend_period": 200,
            "exit_period": 5,
            "atr_mult": 2.5,
        }

    def generate_signals(self, df, **params):
        p = {**self.get_default_params(), **params}
        df = df.copy()

        df["_rsi"] = rsi(df["Close"], p["rsi_period"])
        df["_sma_trend"] = sma(df["Close"], p["trend_period"])
        df["_sma_exit"] = sma(df["Close"], p["exit_period"])
        df["_atr"] = atr(df["High"], df["Low"], df["Close"], 14)

        # 매수 시그널
        df["entry"] = (
            (df["_rsi"] < p["rsi_threshold"]) &
            (df["Close"] > df["_sma_trend"])
        ).astype(int)

        # 매도 시그널
        df["exit"] = (df["Close"] > df["_sma_exit"]).astype(int)

        # 손절가
        df["stop_loss"] = df["Close"] - df["_atr"] * p["atr_mult"]

        # 임시 컬럼 정리
        df.drop(columns=[c for c in df.columns if c.startswith("_")], inplace=True)
        return df


class VolumeBreakout(BaseStrategy):
    """
    전략 2: 거래량 확인 돌파 (VCP)
    - 매수: 레인지 축소 + 거래량 감소 후 RVOL > vol_threshold로 돌파
    - 매도: hold_days 후 또는 목표가 도달
    - 손절: 돌파일 저가 하방
    """
    name = "Volume_Breakout_VCP"
    description = "변동성 축소 후 거래량 동반 돌파"

    def get_default_params(self):
        return {
            "range_lookback": 20,
            "range_threshold": 0.8,  # 레인지가 평균의 80% 이하로 축소
            "vol_threshold": 1.5,    # RVOL 1.5배 이상
            "hold_days": 3,
            "atr_mult": 2.0,
        }

    def generate_signals(self, df, **params):
        p = {**self.get_default_params(), **params}
        df = df.copy()

        # 레인지 축소 감지
        daily_range = df["High"] - df["Low"]
        avg_range = daily_range.rolling(window=p["range_lookback"], min_periods=p["range_lookback"]).mean()
        recent_range = daily_range.rolling(window=5, min_periods=5).mean()
        range_contraction = recent_range / avg_range

        # 거래량 축소 후 급증
        vol_avg = df["Volume"].rolling(window=p["range_lookback"], min_periods=p["range_lookback"]).mean()
        recent_vol = df["Volume"].rolling(window=5, min_periods=5).mean()
        vol_contraction = recent_vol / vol_avg  # 사전 거래량 축소

        current_rvol = df["Volume"] / vol_avg

        # 신고가 돌파
        high_20 = df["High"].rolling(window=p["range_lookback"], min_periods=p["range_lookback"]).max()
        breakout = df["Close"] > high_20.shift(1)

        # 매수 시그널: 레인지 축소 + 거래량 폭증 + 돌파
        df["entry"] = (
            (range_contraction < p["range_threshold"]) &
            (current_rvol > p["vol_threshold"]) &
            breakout
        ).astype(int)

        # 매도: hold_days 후 (backtester에서 처리)
        df["exit"] = pd.Series(0, index=df.index)
        df["hold_days"] = p["hold_days"]

        # 손절: 당일 저가
        df["stop_loss"] = df["Low"]

        return df


class GapDownFade(BaseStrategy):
    """
    전략 3: 갭다운 페이드
    - 매수: 전일 종가 대비 gap_min%~gap_max% 갭다운 + 거래량 정상
    - 매도: 전일 종가 도달 (갭필) 또는 hold_days 후
    - 손절: 시가 대비 -stop_pct%
    """
    name = "GapDown_Fade"
    description = "소형 갭다운 시 갭필 매매"

    def get_default_params(self):
        return {
            "gap_min": -2.0,     # 최소 갭 -2%
            "gap_max": -0.5,     # 최대 갭 -0.5%
            "hold_days": 3,
            "stop_pct": 1.5,     # 시가 대비 -1.5% 손절
        }

    def generate_signals(self, df, **params):
        p = {**self.get_default_params(), **params}
        df = df.copy()

        prev_close = df["Close"].shift(1)
        gap_pct = (df["Open"] - prev_close) / prev_close * 100

        # 거래량 정상 범위 (비정상적 급증 제외)
        vol_avg = df["Volume"].rolling(window=20, min_periods=20).mean()
        vol_normal = df["Volume"] < vol_avg * 5  # 5배 미만

        # 매수 시그널
        df["entry"] = (
            (gap_pct >= p["gap_min"]) &
            (gap_pct <= p["gap_max"]) &
            vol_normal
        ).astype(int)

        # 목표가: 전일 종가 (갭필)
        df["target_price"] = prev_close

        # 매도: hold_days 후
        df["exit"] = pd.Series(0, index=df.index)
        df["hold_days"] = p["hold_days"]

        # 손절: 시가 대비 -stop_pct%
        df["stop_loss"] = df["Open"] * (1 - p["stop_pct"] / 100)

        return df


class VolumeSpikeRSI(BaseStrategy):
    """
    전략 4: 거래량 급증 + RSI 과매도 결합
    - 매수: 거래량 > avg * vol_mult AND RSI(rsi_period) < rsi_threshold AND 종가 > SMA(trend_period)
    - 매도: hold_days 후 또는 RSI > rsi_exit
    - 손절: ATR(14) x atr_mult 하방
    """
    name = "VolumeSpike_RSI"
    description = "거래량 급증 + RSI 과매도 이중 필터"

    def get_default_params(self):
        return {
            "rsi_period": 14,
            "rsi_threshold": 30,
            "rsi_exit": 50,
            "vol_mult": 2.0,
            "trend_period": 50,
            "hold_days": 3,
            "atr_mult": 2.0,
        }

    def generate_signals(self, df, **params):
        p = {**self.get_default_params(), **params}
        df = df.copy()

        df["_rsi"] = rsi(df["Close"], p["rsi_period"])
        df["_sma_trend"] = sma(df["Close"], p["trend_period"])
        df["_atr"] = atr(df["High"], df["Low"], df["Close"], 14)

        vol_avg = df["Volume"].rolling(window=20, min_periods=20).mean()

        # 매수 시그널
        df["entry"] = (
            (df["Volume"] > vol_avg * p["vol_mult"]) &
            (df["_rsi"] < p["rsi_threshold"]) &
            (df["Close"] > df["_sma_trend"])
        ).astype(int)

        # 매도 시그널: RSI 회복
        df["exit"] = (df["_rsi"] > p["rsi_exit"]).astype(int)
        df["hold_days"] = p["hold_days"]

        # 손절가
        df["stop_loss"] = df["Close"] - df["_atr"] * p["atr_mult"]

        df.drop(columns=[c for c in df.columns if c.startswith("_")], inplace=True)
        return df


class VWAPBreakout(BaseStrategy):
    """
    전략 5: VWAP 돌파 + 거래량 확인
    - 매수: 종가가 VWAP 상향 돌파 + 당일 거래량 > 평균 x vol_mult
    - 매도: hold_days 후
    - 손절: VWAP 하방 재이탈
    """
    name = "VWAP_Breakout"
    description = "VWAP 상향 돌파 + 거래량 확인"

    def get_default_params(self):
        return {
            "vol_mult": 1.5,
            "hold_days": 3,
        }

    def generate_signals(self, df, **params):
        p = {**self.get_default_params(), **params}
        df = df.copy()

        df["_vwap"] = vwap_daily(df["High"], df["Low"], df["Close"], df["Volume"])
        vol_avg = df["Volume"].rolling(window=20, min_periods=20).mean()

        prev_close = df["Close"].shift(1)
        prev_vwap = df["_vwap"].shift(1)

        # 매수: 전일 종가 < VWAP → 당일 종가 > VWAP + 거래량 조건
        df["entry"] = (
            (prev_close < prev_vwap) &
            (df["Close"] > df["_vwap"]) &
            (df["Volume"] > vol_avg * p["vol_mult"])
        ).astype(int)

        df["exit"] = pd.Series(0, index=df.index)
        df["hold_days"] = p["hold_days"]

        # 손절: VWAP 하방
        df["stop_loss"] = df["_vwap"]

        df.drop(columns=[c for c in df.columns if c.startswith("_")], inplace=True)
        return df


class OBVDivergence(BaseStrategy):
    """
    전략 6: OBV 다이버전스
    - 매수: 주가 저점 갱신 BUT OBV 저점 미갱신 (상승 다이버전스)
    - 매도: hold_days 후
    """
    name = "OBV_Divergence"
    description = "OBV 상승 다이버전스 감지"

    def get_default_params(self):
        return {
            "lookback": 20,
            "hold_days": 3,
            "atr_mult": 2.0,
        }

    def generate_signals(self, df, **params):
        p = {**self.get_default_params(), **params}
        df = df.copy()

        df["_obv"] = obv(df["Close"], df["Volume"])
        df["_atr"] = atr(df["High"], df["Low"], df["Close"], 14)
        lookback = p["lookback"]

        # 주가 저점
        price_min_recent = df["Close"].rolling(window=lookback, min_periods=lookback).min()
        price_min_prev = df["Close"].shift(lookback).rolling(window=lookback, min_periods=lookback).min()

        # OBV 저점
        obv_min_recent = df["_obv"].rolling(window=lookback, min_periods=lookback).min()
        obv_min_prev = df["_obv"].shift(lookback).rolling(window=lookback, min_periods=lookback).min()

        # 상승 다이버전스: 주가 새 저점, OBV는 아님
        df["entry"] = (
            (price_min_recent < price_min_prev) &
            (obv_min_recent > obv_min_prev)
        ).astype(int)

        df["exit"] = pd.Series(0, index=df.index)
        df["hold_days"] = p["hold_days"]

        # 손절
        df["stop_loss"] = df["Close"] - df["_atr"] * p["atr_mult"]

        df.drop(columns=[c for c in df.columns if c.startswith("_")], inplace=True)
        return df


# 전략 레지스트리
ALL_STRATEGIES = {
    "RSI2": RSI2MeanReversion(),
    "VCP": VolumeBreakout(),
    "GapDown": GapDownFade(),
    "VolSpike_RSI": VolumeSpikeRSI(),
    "VWAP": VWAPBreakout(),
    "OBV_Div": OBVDivergence(),
}


def get_strategy(name):
    """전략 이름으로 전략 객체 반환"""
    if name not in ALL_STRATEGIES:
        raise ValueError(f"알 수 없는 전략: {name}. 사용 가능: {list(ALL_STRATEGIES.keys())}")
    return ALL_STRATEGIES[name]


def list_strategies():
    """모든 전략 목록 출력"""
    for key, strat in ALL_STRATEGIES.items():
        print(f"  {key:15s} | {strat.name:25s} | {strat.description}")
