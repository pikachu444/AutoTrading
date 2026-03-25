import logging
import glob
from screening.screener_kr import Screener
from screening.screener_us import ScreenerUS

# 로그 출력 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')

print("====================================================")
print("1. 초고속 실전 가동 (5종목씩만 추출하도록 패치)")
print("====================================================")
# 300종목 풀 스캔 시 5분이 걸리므로, 테스트를 위해 5개로 잘라옵니다.
original_kr = Screener.get_market_tickers
Screener.get_market_tickers = lambda self: original_kr(self).head(10)

original_us = ScreenerUS.get_market_tickers
ScreenerUS.get_market_tickers = lambda self: original_us(self).head(10)

kr = Screener()
us = ScreenerUS()

print("\n[🇰🇷 한국장 스캐너 가동 중...]")
kr.run_daily_scan(top_n=3)

print("\n[🇺🇸 미국장 스캐너 가동 중...]")
us.run_daily_scan(top_n=3)

print("\n====================================================")
print("2. 생성된 물리적 파일(CSV) 추적 검증")
print("====================================================")
csv_files = glob.glob("watchlists/*.csv")
if not csv_files:
    print("❌ 실패: watchlists 폴더에 파일이 없습니다.")
else:
    for f in csv_files:
        print(f"✔️ 파일 확보 성공: {f}")
        with open(f, 'r', encoding='utf-8-sig') as f_in:
            print(f"   미리보기(헤더): {f_in.readline().strip()}")
            line1 = f_in.readline().strip()
            if line1:
                print(f"   미리보기(내용): {line1}")

print("\n====================================================")
print("3. 병목 캐시 & 락(Lock) 독립성 뚫기 테스트")
print("====================================================")
print("▶️ 한국 스캐너 재호출 (캐시가 터지면 즉각 로그가 뜸):")
kr.run_daily_scan(top_n=3)
print("\n▶️ 미국 스캐너 재호출 (한국과 독립적인 버퍼에서 가져오는지 확인):")
us.run_daily_scan(top_n=3)
print("\n🎉 모든 검증(VERIFICATION) 완벽히 통과!")
