import logging
import pandas as pd
from screener import Screener
from notifier import send_telegram_msg

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

try:
    logging.info("=== [긴급 재발송] 야간 스캔 로직 가동 ===")
    screener = Screener()
    target_list = screener.run_daily_scan(top_n=10)
    
    if target_list:
        lines = [f"{i}위: {st['Name']} ({st['Symbol']}) - RS {st['RS_Rating']:.1f}점" for i, st in enumerate(target_list, 1)]
        msg = "🚀 *[요청하신 야간 긴급 스캔 결과 TOP 10]*\n\n" + "\n".join(lines)
        
        # 텔레그램 발송
        send_telegram_msg(msg)
        
        # 안전한 utf-8-sig 인코딩으로 CSV 저장
        pd.DataFrame(target_list).to_csv('watchlist.csv', index=False, encoding='utf-8-sig')
        logging.info("텔레그램 발송 및 파일 저장이 모두 무사히 완료되었습니다.")
        
    else:
        logging.info("검색된 종목이 없습니다.")
        send_telegram_msg("금일 미너비니 콤보에 걸려든 주도주 종목이 없습니다.")
        
except Exception as e:
    logging.error(f"스캔 실패: {e}")
    send_telegram_msg(f"스캔 중 에러가 발생했습니다: {e}")
