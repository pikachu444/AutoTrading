import time
import schedule
import logging

from trading.engine import BotEngine

# ==============================================================================
# 로깅 (Logging) 설정
# ==============================================================================
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("autotrading.log", encoding="utf-8"), 
        logging.StreamHandler()
    ]
)

def run_scheduler():
    bot = BotEngine()
    
    # 1. 봇 가동 즉시 초기 이벤트 발송 (옵저버에게 알림 위임)
    bot.event_bus.publish("SYSTEM_STARTUP")
    
    # [정기 모니터링 자동화 스케줄러 등록]
    # 2. 매일 오전 07시 30분에 방대한 미국 S&P500 종목 백그라운드 사전 스캔 -> 파일 덤프 & 캐시 메모리 & 텔레그램 발송
    schedule.every().day.at("07:30").do(bot.run_us_scan)
    
    # 3. 매일 오전 08시(장 시작 1시간 전)에 국내 코스피/코스닥 전 종목 백그라운드 사전 스캔 -> 파일 덤프 & 캐시 & 발송
    schedule.every().day.at("08:00").do(bot.run_morning_scan)
    
    # 4. 장 중 정기 감시: 주말/새벽 알아서 필터링되므로 무조건 30분에 한 번씩 타점 검열
    schedule.every(30).minutes.do(bot.bot_job)
    
    logging.info("===========================================")
    logging.info("    📈 하이브리드 자동매매 관제탑 시작 📈   ")
    logging.info("===========================================")
    
    # 영원히 뻗지 않는 대기 메인 루프
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
