"""
한국투자증권 API 브로커 래퍼 모듈

mojito2 라이브러리를 감싸서 자동매매에 필요한 기능을 제공한다.
- 현재가 조회
- 일봉 데이터 조회 (지표 계산용)
- 매수/매도 주문
- 잔고 조회
- 주문 내역 조회
"""
import mojito
import pandas as pd
import time
from datetime import datetime, timedelta
from config import API_KEY, API_SECRET, ACCOUNT_NO, MOCK_TRADING


class Broker:
    """한국투자증권 API 브로커"""

    def __init__(self):
        self.api = mojito.KoreaInvestment(
            api_key=API_KEY,
            api_secret=API_SECRET,
            acc_no=ACCOUNT_NO,
            mock=MOCK_TRADING,
        )
        self.mode = "모의투자" if MOCK_TRADING else "실전매매"
        print(f"[Broker] {self.mode} 모드로 초기화 완료")

    def get_current_price(self, ticker):
        """
        현재가 조회

        Returns:
            dict: {"price": int, "open": int, "high": int, "low": int,
                   "volume": int, "change_pct": float}
        """
        try:
            resp = self.api.fetch_price(ticker)
            output = resp.get("output", {})
            return {
                "price": int(output.get("stck_prpr", 0)),
                "open": int(output.get("stck_oprc", 0)),
                "high": int(output.get("stck_hgpr", 0)),
                "low": int(output.get("stck_lwpr", 0)),
                "volume": int(output.get("acml_vol", 0)),
                "change_pct": float(output.get("prdy_ctrt", 0)),
                "prev_close": int(output.get("stck_sdpr", 0)),
            }
        except Exception as e:
            print(f"[Broker] 현재가 조회 실패 ({ticker}): {e}")
            return None

    def get_daily_ohlcv(self, ticker, days=200):
        """
        일봉 OHLCV 데이터 조회 (지표 계산용)

        Parameters:
            ticker: 종목코드 (예: "005930")
            days: 조회할 일수

        Returns:
            pd.DataFrame: OHLCV DataFrame (Date index)
        """
        try:
            resp = self.api.fetch_ohlcv(
                ticker,
                timeframe="D",
                adj_price=True,
            )
            if not resp or "output2" not in resp:
                return pd.DataFrame()

            records = resp["output2"]
            rows = []
            for r in records:
                try:
                    rows.append({
                        "Date": pd.Timestamp(r["stck_bsop_date"]),
                        "Open": int(r["stck_oprc"]),
                        "High": int(r["stck_hgpr"]),
                        "Low": int(r["stck_lwpr"]),
                        "Close": int(r["stck_clpr"]),
                        "Volume": int(r["acml_vol"]),
                    })
                except (ValueError, KeyError):
                    continue

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            df = df.set_index("Date").sort_index()
            return df.tail(days)

        except Exception as e:
            print(f"[Broker] 일봉 조회 실패 ({ticker}): {e}")
            return pd.DataFrame()

    def buy_market_order(self, ticker, qty):
        """
        시장가 매수 주문

        Returns:
            dict: 주문 결과 {"success": bool, "order_no": str, "message": str}
        """
        try:
            resp = self.api.create_market_buy_order(ticker, qty)
            success = resp.get("rt_cd") == "0"
            order_no = resp.get("output", {}).get("ODNO", "")
            msg = resp.get("msg1", "")
            result = {"success": success, "order_no": order_no, "message": msg}
            print(f"[Broker] 매수 {'성공' if success else '실패'}: {ticker} x {qty}주 | {msg}")
            return result
        except Exception as e:
            print(f"[Broker] 매수 주문 오류 ({ticker}): {e}")
            return {"success": False, "order_no": "", "message": str(e)}

    def sell_market_order(self, ticker, qty):
        """
        시장가 매도 주문

        Returns:
            dict: 주문 결과
        """
        try:
            resp = self.api.create_market_sell_order(ticker, qty)
            success = resp.get("rt_cd") == "0"
            order_no = resp.get("output", {}).get("ODNO", "")
            msg = resp.get("msg1", "")
            result = {"success": success, "order_no": order_no, "message": msg}
            print(f"[Broker] 매도 {'성공' if success else '실패'}: {ticker} x {qty}주 | {msg}")
            return result
        except Exception as e:
            print(f"[Broker] 매도 주문 오류 ({ticker}): {e}")
            return {"success": False, "order_no": "", "message": str(e)}

    def get_balance(self):
        """
        잔고 조회

        Returns:
            dict: {
                "cash": int,  # 예수금
                "total_eval": int,  # 총평가금액
                "total_pnl": int,  # 총손익
                "positions": [
                    {"ticker": str, "name": str, "qty": int, "avg_price": int,
                     "current_price": int, "pnl": int, "pnl_pct": float}
                ]
            }
        """
        try:
            resp = self.api.fetch_balance()
            output1 = resp.get("output1", [])  # 종목별
            output2 = resp.get("output2", [{}])  # 총합

            positions = []
            for item in output1:
                qty = int(item.get("hldg_qty", 0))
                if qty <= 0:
                    continue
                positions.append({
                    "ticker": item.get("pdno", ""),
                    "name": item.get("prdt_name", ""),
                    "qty": qty,
                    "avg_price": int(float(item.get("pchs_avg_pric", 0))),
                    "current_price": int(item.get("prpr", 0)),
                    "pnl": int(item.get("evlu_pfls_amt", 0)),
                    "pnl_pct": float(item.get("evlu_pfls_rt", 0)),
                })

            summary = output2[0] if output2 else {}
            return {
                "cash": int(summary.get("dnca_tot_amt", 0)),
                "total_eval": int(summary.get("tot_evlu_amt", 0)),
                "total_pnl": int(summary.get("evlu_pfls_smtl_amt", 0)),
                "positions": positions,
            }
        except Exception as e:
            print(f"[Broker] 잔고 조회 실패: {e}")
            return {"cash": 0, "total_eval": 0, "total_pnl": 0, "positions": []}

    def get_holding_tickers(self):
        """현재 보유 종목 코드 리스트"""
        balance = self.get_balance()
        return [p["ticker"] for p in balance["positions"]]

    def get_position(self, ticker):
        """특정 종목 보유 정보 조회"""
        balance = self.get_balance()
        for p in balance["positions"]:
            if p["ticker"] == ticker:
                return p
        return None
