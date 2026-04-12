"""
설정 관리 모듈 - API 키, 계좌번호, 전략 파라미터

환경변수 또는 .env 파일에서 민감 정보를 로드한다.
절대 API 키를 코드에 하드코딩하지 말 것!
"""
import os
from pathlib import Path

# .env 파일 로드 (dotenv 없이 직접 파싱)
ENV_FILE = Path(__file__).parent / ".env"


def _load_env_file():
    """간단한 .env 파일 파서"""
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    value = value.strip().strip("'\"")
                    os.environ.setdefault(key.strip(), value)


_load_env_file()


# ──────────────────────────────────────────────
# 한국투자증권 API 설정
# ──────────────────────────────────────────────
API_KEY = os.environ.get("KIS_API_KEY", "")
API_SECRET = os.environ.get("KIS_API_SECRET", "")
ACCOUNT_NO = os.environ.get("KIS_ACCOUNT_NO", "")  # "12345678-01" 형태

# True = 모의투자, False = 실전
MOCK_TRADING = os.environ.get("KIS_MOCK", "true").lower() == "true"


# ──────────────────────────────────────────────
# 전략 파라미터 (RSI(5) 평균회귀 - 최적화 결과)
# ──────────────────────────────────────────────
STRATEGY = {
    "rsi_period": 5,
    "rsi_threshold": 10,       # RSI(5) < 10 매수
    "trend_sma_period": 100,   # 종가 > SMA(100)
    "exit_sma_period": 3,      # 종가 > SMA(3) 매도
    "atr_period": 14,
    "atr_stop_mult": 2.5,      # ATR × 2.5 손절
    "max_hold_days": 3,        # 최대 보유 3일
}


# ──────────────────────────────────────────────
# 리스크 관리
# ──────────────────────────────────────────────
RISK = {
    "total_capital": 10_000_000,      # 총 자본 1,000만원
    "max_positions": 5,               # 동시 보유 최대 5종목
    "risk_per_trade_pct": 1.0,        # 종목당 리스크 1%
    "max_position_pct": 20.0,         # 종목당 최대 20%
    "daily_loss_limit_pct": 3.0,      # 일일 손실 한도 3%
}


# ──────────────────────────────────────────────
# 대상 종목 (KOSPI + KOSDAQ 시총 상위)
# ──────────────────────────────────────────────
# 빈 리스트면 자동으로 시총 상위 종목 로드
WATCHLIST = os.environ.get("KIS_WATCHLIST", "").split(",") if os.environ.get("KIS_WATCHLIST") else []


# ──────────────────────────────────────────────
# 스케줄 설정
# ──────────────────────────────────────────────
# 매매 시그널 체크 시각 (장 마감 30분 전)
SIGNAL_CHECK_TIME = "15:00"
# 손절 체크 간격 (분)
STOP_CHECK_INTERVAL_MIN = 10


# ──────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def validate():
    """설정 유효성 검증"""
    errors = []
    if not API_KEY:
        errors.append("KIS_API_KEY 환경변수가 설정되지 않았습니다")
    if not API_SECRET:
        errors.append("KIS_API_SECRET 환경변수가 설정되지 않았습니다")
    if not ACCOUNT_NO:
        errors.append("KIS_ACCOUNT_NO 환경변수가 설정되지 않았습니다")

    if errors:
        print("\n⚠️  설정 오류:")
        for e in errors:
            print(f"  - {e}")
        print(f"\n  .env 파일 경로: {ENV_FILE}")
        print("  또는 환경변수로 직접 설정하세요.")
        return False
    return True


def print_config():
    """현재 설정 출력 (민감정보 마스킹)"""
    mode = "모의투자" if MOCK_TRADING else "⚠️  실전매매"
    print(f"\n{'='*50}")
    print(f"  자동매매 설정")
    print(f"{'='*50}")
    print(f"  모드:        {mode}")
    print(f"  API Key:     {API_KEY[:4]}...{API_KEY[-4:]}" if len(API_KEY) > 8 else f"  API Key:     (미설정)")
    print(f"  계좌번호:    {ACCOUNT_NO[:4]}...{ACCOUNT_NO[-2:]}" if len(ACCOUNT_NO) > 6 else f"  계좌번호:    (미설정)")
    print(f"  총 자본:     {RISK['total_capital']:,}원")
    print(f"  최대 포지션: {RISK['max_positions']}개")
    print(f"  종목당 리스크: {RISK['risk_per_trade_pct']}%")
    print(f"  전략:        RSI({STRATEGY['rsi_period']}) < {STRATEGY['rsi_threshold']}")
    print(f"  매매 시각:   {SIGNAL_CHECK_TIME}")
    print(f"{'='*50}\n")
