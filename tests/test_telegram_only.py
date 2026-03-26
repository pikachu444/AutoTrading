import time
import logging
from notification.telegram_bot import TelegramBotManager
from core.event_bus import EventBus

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_telegram_test():
    logging.info("========== [텔레그램 봇 단독 테스트] ==========")
    logging.info("이 스크립트는 한국투자증권 API 연결 없이 텔레그램 기능만 독립적으로 테스트합니다.")
    
    event_bus = EventBus()
    bot = TelegramBotManager(event_bus)
    bot.start_polling()
    
    try:
        logging.info("대기 모드 진입. 스마트폰 텔레그램에서 봇에게 /start 또는 /rs 를 전송해보세요!")
        logging.info("종료하려면 Ctrl+C 를 누르세요.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop_polling()
        logging.info("텔레그램 테스트 스크립트가 안전하게 종료되었습니다.")

if __name__ == "__main__":
    run_telegram_test()
