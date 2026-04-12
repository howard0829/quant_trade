# 3일 단기매매 수익 전략 연구 & 자동매매 시스템

주가와 거래량을 기준으로 **매수 후 3거래일 이내에 수익이 나는 조건**을 체계적으로 탐색하고,
발견된 최적 전략을 **한국투자증권 API로 자동매매**하는 시스템입니다.

---

## 연구 결과 요약

12년치 데이터(2014~2026)로 KOSPI 50종목, KOSDAQ 50종목, S&P500 15종목에서 6개 전략을 백테스팅한 결과:

### 최적 전략: RSI(5) 평균회귀

| 시장 | 기본 파라미터 | 최적화 후 |
|------|-------------|----------|
| **KOSPI 50** | 승률 55.3%, +0.25% | **승률 82.8%, +1.78%, PF 6.03** |
| **KOSDAQ 50** | 승률 54.0%, +0.46% | **승률 80.0%, +2.84%, PF 7.34** |
| **S&P500 15** | 승률 60.0%, +0.27% | - |

```
매수: RSI(5) < 10 AND 종가 > SMA(100)
매도: 종가 > SMA(3)
손절: ATR(14) × 2.5 하방
```

6개 전략 중 RSI(5) 평균회귀만이 **양 시장 모두에서 안정적으로 수익**을 기록했습니다.

---

## 프로젝트 구조

```
stock_strategy/
│
├── [백테스트 엔진]
│   ├── main.py                 # 백테스트 CLI 실행 파이프라인
│   ├── data_loader.py          # 데이터 수집 (pykrx, FinanceDataReader, yfinance)
│   ├── indicators.py           # 기술적 지표 (RSI, OBV, RVOL, VWAP, ATR, SMA)
│   ├── strategies.py           # 6개 전략 시그널 생성
│   ├── backtester.py           # 매매 시뮬레이션 엔진
│   ├── optimizer.py            # 파라미터 그리드 서치 + Walk-Forward 검증
│   ├── analyzer.py             # 성과 심층 분석 (연도별, 시장환경별)
│   └── report_generator.py     # Markdown 리포트 생성
│
├── [자동매매 봇]
│   └── auto_trader/
│       ├── main.py             # 자동매매 CLI
│       ├── config.py           # 설정 관리 (환경변수/.env)
│       ├── broker.py           # 한국투자증권 API 래퍼 (mojito2)
│       ├── signal_generator.py # RSI(5) 실시간 시그널 생성
│       ├── trader.py           # 자동 매수/매도 실행기
│       ├── risk_manager.py     # 포지션 사이징 + 손절 관리
│       ├── trade_logger.py     # 거래 기록 CSV 로깅
│       ├── scheduler.py        # 장중 자동 스케줄러
│       ├── setup_guide.py      # 대화형 초기 설정 가이드
│       ├── run_mock.sh         # 모의투자 실행 스크립트
│       ├── run_live.sh         # 실전매매 실행 스크립트
│       ├── .env.example        # API 키 설정 템플릿
│       └── logs/               # 거래 로그
│
└── reports/                    # 생성된 분석 리포트
    ├── final_research_report.md
    ├── extended_report_KOSPI50_KOSDAQ50.md
    ├── optimization_RSI2_KOSPI.md
    ├── optimization_RSI2_KOSDAQ.md
    ├── auto_trading_guide.md
    └── backtest_report_*.md
```

---

## 1. 백테스트 사용법

### 필요 라이브러리

```bash
pip install pykrx finance-datareader yfinance vectorbt pandas numpy tabulate
```

### 실행 예시

```bash
cd /Users/howard/Project/stock_strategy

# 전략 목록 확인
python main.py --list

# 단일 종목 테스트 (삼성전자, 전 전략 적용)
python main.py --ticker 005930 --market KOSPI

# KOSPI 상위 50종목 백테스트
python main.py --market KOSPI --max 50

# KOSDAQ 50종목 백테스트
python main.py --market KOSDAQ --max 50

# S&P500 백테스트
python main.py --market SP500 --max 30

# RSI2 파라미터 최적화
python main.py --optimize RSI2 --market KOSPI --max 50

# Walk-Forward 과적합 검증
python main.py --walkforward RSI2 --market KOSPI --max 5

# 전체 시장 일괄 실행 (KOSPI + KOSDAQ + SP500)
python main.py --full --max 50
```

### 테스트한 6개 전략

| # | 전략 | 핵심 로직 | 결과 |
|---|------|----------|------|
| 1 | **RSI(2) 평균회귀** | RSI 과매도 진입 → SMA 돌파 청산 | **유효** |
| 2 | 거래량 확인 돌파 (VCP) | 변동성 축소 후 거래량 동반 돌파 | 시그널 부족 |
| 3 | 갭다운 페이드 | 소형 갭다운 시 갭필 매매 | 비유효 |
| 4 | 거래량급증 + RSI | 이중 필터 | 시그널 극소 |
| 5 | VWAP 돌파 | VWAP 상향 돌파 + 거래량 확인 | KOSDAQ 한정 |
| 6 | OBV 다이버전스 | 주가 vs OBV 괴리 감지 | 한계적 |

---

## 2. 자동매매 사용법

### 사전 준비

1. **한국투자증권 계좌 개설** (앱에서 비대면 개설, ~10분)
2. **API 키 발급**: https://apiportal.koreainvestment.com → 모의투자 키 발급
3. **대화형 설정 가이드 실행**:
   ```bash
   cd auto_trader
   python setup_guide.py
   ```
   또는 수동으로 `.env` 파일 작성:
   ```bash
   cp .env.example .env
   vi .env  # API_KEY, API_SECRET, ACCOUNT_NO 입력
   ```

### 모의투자 (연습)

```bash
cd auto_trader

./run_mock.sh test      # API 접속 테스트
./run_mock.sh once      # 1회 매매 사이클 실행
./run_mock.sh status    # 포트폴리오 현황
./run_mock.sh history   # 거래 내역
./run_mock.sh           # 스케줄러 자동 실행 (09:05~15:35)
```

### 실전매매

```bash
./run_live.sh test      # 실전 API 접속 테스트
./run_live.sh once      # 1회 실전 매매 ("yes" 입력 필요)
./run_live.sh           # 스케줄러 자동 실행 ("yes" 입력 필요)
```

### 매일 자동 실행 (macOS launchd)

```bash
# 등록 (매일 월~금 08:55 자동 시작 → 15:35 자동 종료)
launchctl load ~/Library/LaunchAgents/com.howard.autotrader.plist

# 해제
launchctl unload ~/Library/LaunchAgents/com.howard.autotrader.plist

# 상태 확인
launchctl list | grep autotrader
```

현재 launchd는 **모의투자(`run_mock.sh`)**로 설정되어 있습니다.
실전 전환 시 plist 파일에서 `run_mock.sh` → `run_live.sh --yes`로 변경합니다.

### 자동매매 일일 스케줄

| 시각 | 동작 |
|------|------|
| 08:55 | macOS launchd가 봇 자동 시작 |
| 09:05 | 포트폴리오 현황 확인 |
| 10분마다 | 보유종목 손절 체크 (장중) |
| **15:00** | **매도 체크 → 매수 스캔 → 주문 실행** |
| 15:25 | 장 마감 전 최종 확인 |
| 15:35 | 봇 자동 종료 |

### 로그 확인

```bash
# 모의투자 로그
tail -f auto_trader/logs/mock_20260414.log

# 실전매매 로그
tail -f auto_trader/logs/live_20260414.log

# 거래 내역 CSV
cat auto_trader/logs/trades.csv
```

---

## 3. 리스크 관리

| 항목 | 설정값 |
|------|--------|
| 총 자본 | 10,000,000원 |
| 종목당 최대 투자 | 20% (2,000,000원) |
| 동시 보유 | 최대 5종목 |
| 종목당 리스크 | 1% (100,000원) |
| 손절 | ATR(14) × 2.5 |
| 일일 손실 한도 | -3% 도달 시 매매 중단 |

설정 변경: `auto_trader/config.py`의 `RISK` 딕셔너리 수정

---

## 4. 기술 스택

| 용도 | 도구 |
|------|------|
| 한국 주식 데이터 | pykrx, FinanceDataReader |
| 미국 주식 데이터 | yfinance |
| 기술적 지표 | 자체 구현 (pandas/numpy) |
| 백테스트 | 자체 구현 (event-driven) |
| 자동매매 API | 한국투자증권 OpenAPI (mojito2) |
| 스케줄링 | schedule (Python) + launchd (macOS) |
| 언어 | Python 3.10 |

---

## 주의사항

- **과거 성과가 미래 수익을 보장하지 않습니다**
- 백테스트에는 생존자 편향(survivorship bias)이 포함될 수 있습니다
- 최적화된 파라미터는 3~6개월마다 재검증이 필요합니다
- **반드시 모의투자로 최소 2~4주 테스트 후 실전 전환하세요**
- API 키는 절대 코드에 하드코딩하지 마세요 (`.env` 사용)
- 시세조종, 허수 주문 등은 불법입니다
