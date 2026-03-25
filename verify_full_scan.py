import logging
import time
import glob
from screening.screener_us import ScreenerUS

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("🇺🇸 [전체 S&P 500 종목 리얼 스캔 진입!]")
start = time.time()
us = ScreenerUS()
targets = us.run_daily_scan(top_n=10)
end = time.time()

print("====================================")
print(f"🇺🇸 [실제 S&P 500 스캔 완료! (소요 시간: {end-start:.1f}초)]")

if not targets:
    print("오늘 조건을 통과한 대장주가 0개입니다.")
else:
    for idx, t in enumerate(targets, 1):
        print(f"[{idx}위] {t['Symbol']:<5} | RS: {t['RS_Rating']:>4.1f} | {t['Name']}")

print("\n[watchlists 폴더 내 마지막으로 생성된 csv 파일 덤프 확인]")
csv_files = glob.glob("watchlists/watchlist_us_*.csv")
if csv_files:
    latest = sorted(csv_files)[-1]
    print(f"✔️ 기록 파일: {latest}")
    with open(latest, 'r', encoding='utf-8-sig') as f_in:
        print("헤더:", f_in.readline().strip())
        print("1위:", f_in.readline().strip())
        print("2위:", f_in.readline().strip())
print("====================================")
