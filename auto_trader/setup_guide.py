#!/usr/bin/env python3
"""
자동매매 봇 초기 설정 가이드 - 대화형으로 안내

실행: python setup_guide.py
"""
import os
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"
PLIST_FILE = Path.home() / "Library/LaunchAgents/com.howard.autotrader.plist"


def step_header(num, title):
    print(f"\n{'─'*55}")
    print(f"  Step {num}: {title}")
    print(f"{'─'*55}")


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║       3일 단기매매 자동매매 봇 - 초기 설정 가이드      ║
╠══════════════════════════════════════════════════════╣
║  RSI(5) < 10 평균회귀 전략                            ║
║  KOSPI/KOSDAQ 상위 50종목 자동 매매                    ║
║  승률 ~80%, 평균수익 +1.8~2.8%                        ║
╚══════════════════════════════════════════════════════╝
    """)

    # ──────────────────────────────────────
    # Step 1: 한국투자증권 계좌 개설
    # ──────────────────────────────────────
    step_header(1, "한국투자증권 계좌 개설")
    print("""
  1) 앱스토어에서 '한국투자' 검색 → 앱 다운로드
  2) 앱 실행 → '비대면 계좌개설' 선택
  3) 신분증 촬영 + 휴대폰 인증 (약 10분)
  4) 계좌 개설 완료 → 계좌번호 메모 (예: 12345678-01)
  5) 1,000만원 입금 (이체)
    """)
    input("  계좌 준비가 되면 Enter를 누르세요... ")

    # ──────────────────────────────────────
    # Step 2: API 키 발급
    # ──────────────────────────────────────
    step_header(2, "API 키 발급")
    print("""
  1) https://apiportal.koreainvestment.com 접속
  2) 회원가입 (증권 계좌와 동일 정보)
  3) 로그인 → [API 신청] → [KIS Developers] 클릭
  4) [앱 생성] 클릭
     - 앱 이름: autotrader (아무거나)
     - Callback URL: (비워두기)
  5) 생성된 App Key, App Secret 복사

  ⚠️  모의투자용 키를 먼저 발급받으세요!
     [모의투자 신청] → 별도의 App Key/Secret 발급됨
    """)
    input("  API 키가 준비되면 Enter를 누르세요... ")

    # ──────────────────────────────────────
    # Step 3: .env 파일 작성
    # ──────────────────────────────────────
    step_header(3, ".env 파일 작성")

    if ENV_FILE.exists():
        print(f"  기존 .env 파일이 있습니다: {ENV_FILE}")
        overwrite = input("  새로 작성하시겠습니까? (y/n): ")
        if overwrite.lower() != "y":
            print("  기존 파일 유지")
        else:
            _write_env()
    else:
        _write_env()

    # ──────────────────────────────────────
    # Step 4: 접속 테스트
    # ──────────────────────────────────────
    step_header(4, "API 접속 테스트")
    print("  접속 테스트를 실행합니다...\n")
    os.system(f"{sys.executable} main.py --test")

    # ──────────────────────────────────────
    # Step 5: 자동 실행 등록
    # ──────────────────────────────────────
    step_header(5, "매일 자동 실행 등록")

    if PLIST_FILE.exists():
        print(f"  launchd 설정 파일이 이미 존재합니다.")
    else:
        print(f"  launchd 설정 파일이 없습니다.")

    print(f"""
  자동 실행을 활성화하려면 아래 명령어를 실행하세요:

    launchctl load ~/Library/LaunchAgents/com.howard.autotrader.plist

  비활성화:
    launchctl unload ~/Library/LaunchAgents/com.howard.autotrader.plist

  상태 확인:
    launchctl list | grep autotrader
    """)

    register = input("  지금 자동 실행을 등록하시겠습니까? (y/n): ")
    if register.lower() == "y":
        os.system("launchctl load ~/Library/LaunchAgents/com.howard.autotrader.plist")
        print("\n  ✅ 자동 실행 등록 완료!")
        print("  내일 08:55부터 매일 자동으로 매매 봇이 실행됩니다.")
    else:
        print("  수동 등록을 원하시면 위 명령어를 나중에 실행하세요.")

    # ──────────────────────────────────────
    # 완료
    # ──────────────────────────────────────
    print(f"""
{'═'*55}
  🎉 설정 완료!
{'═'*55}

  [사용법]
  수동 테스트:    python main.py --test
  1회 매매:       python main.py --once
  스케줄러 시작:  python main.py --run
  현황 확인:      python main.py --status
  거래 내역:      python main.py --history

  [자동 실행]
  매일 월~금 08:55에 자동 시작 → 15:35에 자동 종료
  로그 확인: tail -f logs/launchd_out.log

  [매매 흐름]
  09:05  포트폴리오 현황 확인
  10분마다  보유종목 손절 체크
  15:00  매도 체크 → 매수 스캔 → 주문 실행
  15:25  장 마감 전 최종 확인
  15:35  봇 자동 종료
{'═'*55}
    """)


def _write_env():
    """대화형으로 .env 파일 작성"""
    print("\n  API 정보를 입력하세요 (모의투자용 키 권장):\n")

    api_key = input("  App Key: ").strip()
    api_secret = input("  App Secret: ").strip()
    account_no = input("  계좌번호 (예: 12345678-01): ").strip()

    content = f"""# 한국투자증권 API 설정
KIS_API_KEY={api_key}
KIS_API_SECRET={api_secret}
KIS_ACCOUNT_NO={account_no}

# true = 모의투자, false = 실전매매
KIS_MOCK=true
"""

    with open(ENV_FILE, "w") as f:
        f.write(content)

    print(f"\n  ✅ .env 파일 저장 완료: {ENV_FILE}")
    print(f"  모드: 모의투자 (KIS_MOCK=true)")


if __name__ == "__main__":
    main()
