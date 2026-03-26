import logging
from screening.screener_kr import Screener
from screening.screener_us import ScreenerUS

logging.basicConfig(level=logging.INFO, format='%(message)s')

def full_refresh():
    print("🇰🇷 [한국장 전수조사 중... (KOSPI 200/KOSDAQ 100)]")
    kr = Screener()
    kr_targets = kr.run_daily_scan(top_n=10)
    print(f"   => {len(kr_targets)}종목 발굴!")

    print("\n🇺🇸 [미국장 전수조사 중... (S&P 500)]")
    us = ScreenerUS()
    us_targets = us.run_daily_scan(top_n=10)
    print(f"   => {len(us_targets)}종목 발굴!")

    print("\n✅ 모든 워치리스트가 'watchlists/' 폴더에 최신화되었습니다!")

if __name__ == "__main__":
    full_refresh()
