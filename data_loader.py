"""
데이터 수집 모듈 - 한국(KRX) 및 미국(S&P500) 주식 OHLCV 데이터 수집
"""
import time
import pandas as pd
from pykrx import stock as krx
import yfinance as yf
import FinanceDataReader as fdr


def get_krx_stock_list(market="ALL"):
    """KRX 종목 리스트 조회 (KOSPI/KOSDAQ/ALL)"""
    today = pd.Timestamp.now().strftime("%Y%m%d")
    if market == "ALL":
        kospi = krx.get_market_ticker_list(today, market="KOSPI")
        kosdaq = krx.get_market_ticker_list(today, market="KOSDAQ")
        tickers = kospi + kosdaq
    else:
        tickers = krx.get_market_ticker_list(today, market=market)

    result = []
    for ticker in tickers:
        name = krx.get_market_ticker_name(ticker)
        result.append({"ticker": ticker, "name": name, "market": market})
    return pd.DataFrame(result)


def get_krx_ohlcv(ticker, start_date, end_date):
    """KRX 개별 종목 OHLCV 데이터 조회"""
    df = krx.get_market_ohlcv(start_date, end_date, ticker)
    if df.empty:
        return df
    # pykrx 컬럼: 시가, 고가, 저가, 종가, 거래량, 등락률
    df = df.rename(columns={"시가": "Open", "고가": "High", "저가": "Low",
                            "종가": "Close", "거래량": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.index.name = "Date"
    return df


def get_krx_bulk_ohlcv(tickers, start_date, end_date, delay=1.0):
    """KRX 다수 종목 OHLCV 일괄 조회 (딜레이 포함)"""
    all_data = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers):
        try:
            df = get_krx_ohlcv(ticker, start_date, end_date)
            if not df.empty and len(df) > 50:
                all_data[ticker] = df
            if i < total - 1:
                time.sleep(delay)
        except Exception as e:
            print(f"[{i+1}/{total}] {ticker} 실패: {e}")
            continue
        if (i + 1) % 50 == 0:
            print(f"[{i+1}/{total}] 수집 진행 중...")
    print(f"총 {len(all_data)}개 종목 수집 완료")
    return all_data


def get_kospi200_tickers():
    """KOSPI200 구성 종목 티커 조회"""
    try:
        df = fdr.StockListing("KOSPI")
        # 시가총액 상위 200종목으로 근사
        df = df.nlargest(200, "Marcap") if "Marcap" in df.columns else df.head(200)
        return df["Code"].tolist()
    except Exception:
        # fallback: pykrx에서 KOSPI 전체 조회
        today = pd.Timestamp.now().strftime("%Y%m%d")
        return krx.get_market_ticker_list(today, market="KOSPI")[:200]


def get_kosdaq150_tickers():
    """KOSDAQ150 구성 종목 티커 조회"""
    try:
        df = fdr.StockListing("KOSDAQ")
        df = df.nlargest(150, "Marcap") if "Marcap" in df.columns else df.head(150)
        return df["Code"].tolist()
    except Exception:
        today = pd.Timestamp.now().strftime("%Y%m%d")
        return krx.get_market_ticker_list(today, market="KOSDAQ")[:150]


def get_sp500_tickers():
    """S&P500 구성 종목 티커 조회"""
    try:
        table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        return table[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception:
        # fallback: 주요 대형주
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                "BRK-B", "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG"]


def get_us_ohlcv(ticker, start_date, end_date):
    """미국 개별 종목 OHLCV 데이터 조회 (yfinance)"""
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty:
            return df
        # yfinance가 MultiIndex columns를 반환하는 경우 처리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.index.name = "Date"
        return df
    except Exception as e:
        print(f"{ticker} 데이터 조회 실패: {e}")
        return pd.DataFrame()


def get_us_bulk_ohlcv(tickers, start_date, end_date):
    """미국 다수 종목 OHLCV 일괄 조회"""
    all_data = {}
    total = len(tickers)
    # yfinance 배치 다운로드
    try:
        batch_df = yf.download(tickers, start=start_date, end=end_date,
                               group_by="ticker", progress=False, threads=True)
        for ticker in tickers:
            try:
                if isinstance(batch_df.columns, pd.MultiIndex):
                    df = batch_df[ticker].dropna()
                else:
                    df = batch_df.dropna()
                if len(df) > 50:
                    df = df[["Open", "High", "Low", "Close", "Volume"]]
                    all_data[ticker] = df
            except (KeyError, Exception):
                continue
    except Exception:
        # fallback: 개별 다운로드
        for i, ticker in enumerate(tickers):
            df = get_us_ohlcv(ticker, start_date, end_date)
            if not df.empty and len(df) > 50:
                all_data[ticker] = df
            if (i + 1) % 50 == 0:
                print(f"[{i+1}/{total}] 수집 진행 중...")
    print(f"총 {len(all_data)}개 종목 수집 완료 (US)")
    return all_data


def load_market_data(market, start_date="20140101", end_date=None, max_tickers=None):
    """
    시장별 데이터 로딩 통합 함수

    Parameters:
        market: "KOSPI", "KOSDAQ", "SP500"
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD), None이면 오늘
        max_tickers: 최대 종목 수 제한 (테스트용)

    Returns:
        dict[str, pd.DataFrame]: {ticker: OHLCV DataFrame}
    """
    if end_date is None:
        end_date = pd.Timestamp.now().strftime("%Y%m%d")

    if market == "KOSPI":
        tickers = get_kospi200_tickers()
    elif market == "KOSDAQ":
        tickers = get_kosdaq150_tickers()
    elif market == "SP500":
        tickers = get_sp500_tickers()
    else:
        raise ValueError(f"지원하지 않는 시장: {market}")

    if max_tickers:
        tickers = tickers[:max_tickers]

    print(f"[{market}] {len(tickers)}개 종목 데이터 수집 시작...")

    if market in ("KOSPI", "KOSDAQ"):
        # KRX용 날짜 형식
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        return get_krx_bulk_ohlcv(tickers, start, end)
    else:
        # US용 날짜 형식 (YYYY-MM-DD)
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        return get_us_bulk_ohlcv(tickers, start, end)


if __name__ == "__main__":
    # 테스트: 삼성전자 최근 1년 데이터
    df = get_krx_ohlcv("005930", "20240101", "20250411")
    print(f"삼성전자 데이터: {len(df)}일")
    print(df.tail())
