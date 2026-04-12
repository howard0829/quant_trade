"""
로컬 시뮬레이션 브로커 - API 연결 없이 실전과 동일한 매매 시뮬레이션

가격 데이터:
  - 장중: 네이버 금융에서 실시간 시�� 조회 (~5-15초 딜레이)
  - 장외: pykrx에서 최근 종가 조회
  → 실전 매매와 동일한 시점에 동일한 가격으로 매매 시뮬레이션

broker.py와 동일한 인터페이스를 제공하여 trader.py에서 교체 가능.
"""
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from pykrx import stock as krx
from config import RISK, LOG_DIR


PORTFOLIO_FILE = LOG_DIR / "sim_portfolio.json"
NAVER_API = "https://m.stock.naver.com/api/stock/{}/basic"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}


# ── 실시간 시세 조회 ──

def _fetch_realtime_price(ticker):
    """
    네이버 금융에서 실시간 시세 ���회 (장중 ~5-15초 딜레이)
    장 마감 후에는 당일 종가를 반환.
    """
    try:
        resp = requests.get(NAVER_API.format(ticker), headers=NAVER_HEADERS, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()

        # 현재가 파싱 (쉼표 제거)
        def _int(val):
            if val is None:
                return 0
            return int(str(val).replace(",", "").replace("+", "").replace("-", ""))

        price = _int(data.get("currentPrice"))
        if price <= 0:
            return None

        # 전일 종가
        prev_close = _int(data.get("previousClosePrice"))
        change_pct = 0
        if prev_close > 0:
            change_pct = (price - prev_close) / prev_close * 100

        return {
            "price": price,
            "open": _int(data.get("openPrice")),
            "high": _int(data.get("highPrice")),
            "low": _int(data.get("lowPrice")),
            "volume": _int(data.get("accumulatedTradingVolume")),
            "change_pct": round(change_pct, 2),
            "prev_close": prev_close,
            "source": "naver_realtime",
        }
    except Exception:
        return None


def _fetch_pykrx_price(ticker):
    """pykrx에서 최근 종가 조회 (fallback)"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        df = krx.get_market_ohlcv(start, today, ticker)
        if df.empty:
            return None
        df = df.rename(columns={
            "시가": "Open", "고가": "High", "저가": "Low",
            "종가": "Close", "거래량": "Volume", "등락률": "Change"
        })
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last
        return {
            "price": int(last["Close"]),
            "open": int(last["Open"]),
            "high": int(last["High"]),
            "low": int(last["Low"]),
            "volume": int(last["Volume"]),
            "change_pct": float(last.get("Change", 0)),
            "prev_close": int(prev["Close"]),
            "source": "pykrx_daily",
        }
    except Exception:
        return None


class SimBroker:
    """로컬 시뮬레이션 브로커 (API 불필요, 실시간 시세 사용)"""

    def __init__(self):
        self._portfolio = self._load_portfolio()
        self._price_cache = {}  # {ticker: {data, timestamp}} - 과도한 요청 방지
        self._cache_ttl = 10    # 캐시 유효시간 (초)
        print(f"[SimBroker] 로컬 시뮬레이션 모드 (네이버 실시간 시세)")

    # ── 포트폴리오 영속화 ──

    def _load_portfolio(self):
        if PORTFOLIO_FILE.exists():
            with open(PORTFOLIO_FILE) as f:
                return json.load(f)
        return {"cash": RISK["total_capital"], "positions": {}}

    def _save_portfolio(self):
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(self._portfolio, f, indent=2, ensure_ascii=False)

    # ── 시세 조회 (실시간 우선, pykrx fallback) ──

    def get_current_price(self, ticker):
        """
        실시간 시세 조회
        1순위: 네이버 금융 (장중 실시간, ~5-15초 딜레이)
        2순위: pykrx (장 마감 후 종가)
        """
        # 캐시 확인
        now = time.time()
        if ticker in self._price_cache:
            cached = self._price_cache[ticker]
            if now - cached["timestamp"] < self._cache_ttl:
                return cached["data"]

        # 1순위: 네이버 실시간
        result = _fetch_realtime_price(ticker)

        # 2순위: pykrx fallback
        if result is None:
            result = _fetch_pykrx_price(ticker)

        if result:
            self._price_cache[ticker] = {"data": result, "timestamp": now}

        return result

    def get_daily_ohlcv(self, ticker, days=200):
        """pykrx에서 일봉 OHLCV 조회 (지표 계산용)"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=int(days * 1.5))).strftime("%Y%m%d")
            df = krx.get_market_ohlcv(start, today, ticker)
            if df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                "시가": "Open", "고가": "High", "저가": "Low",
                "종가": "Close", "거래량": "Volume"
            })
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.index.name = "Date"
            time.sleep(0.3)  # pykrx 요청 간격
            return df.tail(days)
        except Exception as e:
            print(f"[SimBroker] 일봉 조회 실패 ({ticker}): {e}")
            return pd.DataFrame()

    # ── 매매 (실시간 가격으로 체결) ──

    def buy_market_order(self, ticker, qty):
        """시뮬레이션 매수 - 실시간 가격으로 체결"""
        price_info = self.get_current_price(ticker)
        if not price_info:
            return {"success": False, "order_no": "", "message": "가격 조회 실패"}

        price = price_info["price"]
        source = price_info.get("source", "unknown")
        cost = price * qty
        commission = int(cost * 0.00015)
        total_cost = cost + commission

        if total_cost > self._portfolio["cash"]:
            return {"success": False, "order_no": "",
                    "message": f"예수금 부족: {self._portfolio['cash']:,} < {total_cost:,}"}

        self._portfolio["cash"] -= total_cost
        name = krx.get_market_ticker_name(ticker)

        if ticker in self._portfolio["positions"]:
            pos = self._portfolio["positions"][ticker]
            old_total = pos["avg_price"] * pos["qty"]
            pos["qty"] += qty
            pos["avg_price"] = int((old_total + cost) / pos["qty"])
        else:
            self._portfolio["positions"][ticker] = {
                "qty": qty, "avg_price": price, "name": name
            }

        self._save_portfolio()
        order_no = f"SIM-{datetime.now().strftime('%H%M%S')}"
        print(f"[SimBroker] 매수: {name}({ticker}) {qty}주 @ {price:,}원 [{source}]")
        return {"success": True, "order_no": order_no, "message": f"매수 완료 ({source})"}

    def sell_market_order(self, ticker, qty):
        """시뮬레이션 매도 - 실시간 가격으로 체결"""
        if ticker not in self._portfolio["positions"]:
            return {"success": False, "order_no": "", "message": "보유하지 않은 종목"}

        pos = self._portfolio["positions"][ticker]
        if qty > pos["qty"]:
            qty = pos["qty"]

        price_info = self.get_current_price(ticker)
        if not price_info:
            return {"success": False, "order_no": "", "message": "가격 조회 실패"}

        price = price_info["price"]
        source = price_info.get("source", "unknown")
        proceeds = price * qty
        commission = int(proceeds * 0.00015)
        tax = int(proceeds * 0.0018)
        net = proceeds - commission - tax

        self._portfolio["cash"] += net
        name = pos.get("name", ticker)
        entry_price = pos["avg_price"]
        pnl = net - entry_price * qty
        pnl_pct = pnl / (entry_price * qty) * 100

        pos["qty"] -= qty
        if pos["qty"] <= 0:
            del self._portfolio["positions"][ticker]

        self._save_portfolio()
        order_no = f"SIM-{datetime.now().strftime('%H%M%S')}"
        print(f"[SimBroker] 매도: {name}({ticker}) {qty}주 @ {price:,}원 "
              f"(손익 {pnl:+,}원, {pnl_pct:+.1f}%) [{source}]")
        return {"success": True, "order_no": order_no, "message": f"매도 완료 ({source})"}

    # ── 잔고 조회 ──

    def get_balance(self):
        positions = []
        total_eval = self._portfolio["cash"]

        for ticker, pos in self._portfolio["positions"].items():
            price_info = self.get_current_price(ticker)
            current_price = price_info["price"] if price_info else pos["avg_price"]
            eval_amt = current_price * pos["qty"]
            pnl = eval_amt - pos["avg_price"] * pos["qty"]
            pnl_pct = pnl / (pos["avg_price"] * pos["qty"]) * 100 if pos["avg_price"] > 0 else 0

            positions.append({
                "ticker": ticker,
                "name": pos.get("name", ticker),
                "qty": pos["qty"],
                "avg_price": pos["avg_price"],
                "current_price": current_price,
                "pnl": pnl,
                "pnl_pct": round(pnl_pct, 2),
            })
            total_eval += eval_amt

        total_pnl = total_eval - RISK["total_capital"]
        return {
            "cash": self._portfolio["cash"],
            "total_eval": total_eval,
            "total_pnl": total_pnl,
            "positions": positions,
        }

    def get_holding_tickers(self):
        return list(self._portfolio["positions"].keys())

    def get_position(self, ticker):
        balance = self.get_balance()
        for p in balance["positions"]:
            if p["ticker"] == ticker:
                return p
        return None

    def reset(self):
        self._portfolio = {"cash": RISK["total_capital"], "positions": {}}
        self._save_portfolio()
        print(f"[SimBroker] 포트폴리오 초기화: {RISK['total_capital']:,}원")
