import logging
from screening.screener_kr import Screener
from screening.screener_us import ScreenerUS

logging.basicConfig(level=logging.INFO, format='%(message)s')

def full_refresh():
    kr = Screener()
    # 1. 한국 대형주 스캔
    print("🇰🇷 [1/3] 한국 대형 주도주 스캔 중... (시총 상위 200)")
    kr_large = kr.run_daily_scan(top_n=10, mode="LARGE")
    print(f"   => {len(kr_large)}종목 발굴!")

    # 2. 한국 중소형 성장주 스캔
    print("\n🚀 [2/3] 한국 중소형 성장주 스캔 중... (거래대금 폭발)")
    kr_growth = kr.run_daily_scan(top_n=10, mode="GROWTH")
    print(f"   => {len(kr_growth)}종목 발굴!")

    # 3. 미국 우량주 스캔
    print("\n🇺🇸 [3/3] 미국 S&P 500 우량주 스캔 중...")
    us = ScreenerUS()
    us_targets = us.run_daily_scan(top_n=10)
    print(f"   => {len(us_targets)}종목 발굴!")

    print("\n✅ 모든 워치리스트(Large / Growth / US)가 최신화되었습니다!")


if __name__ == "__main__":
    full_refresh()
