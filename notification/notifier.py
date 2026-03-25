import requests
import logging
from core.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_msg(message: str, chat_id: str = None):
    """
    [텔레그램 푸쉬 알림 발송 모듈]
    지정된 텔레그램 챗방으로 즉각적인 메시지를 전송합니다.
    chat_id를 입력하지 않으면 config.py에 설정된 관리자의 채팅방으로 기본 전송됩니다.
    """
    from core.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or "여기에" in TELEGRAM_TOKEN:
        logging.debug("텔레그램 토큰이 설정되지 않아 알림 발송이 생략되었습니다.")
        return
        
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not target_chat or str(target_chat) == "" or "여기에" in str(target_chat):
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        res = requests.post(url, json=payload, timeout=5)
        res.raise_for_status()
        logging.info(f"[Telegram] 알림 발송 성공! (To: {target_chat})")
    except Exception as e:
        logging.error(f"[Telegram] 알림 발송 실패: {e}")

class NotificationService:
    """
    [통합 알림 서비스 Obsever]
    EventBus를 통해 시스템 안에서 돌아다니는 각종 이벤트(매수/매도/스캔)를 모니터링하다가
    발생하는 즉시 텔레그램 등의 메신저 포맷으로 변경하여 발송합니다.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        # 이벤트 버스 구독 등록 (관심 있는 신호만 감지합니다)
        self.event_bus.subscribe("SYSTEM_STARTUP", self._on_system_startup)
        self.event_bus.subscribe("SCAN_COMPLETED", self._on_scan_completed)
        self.event_bus.subscribe("US_SCAN_COMPLETED", self._on_us_scan_completed)
        self.event_bus.subscribe("SCAN_ERROR", self._on_scan_error)
        self.event_bus.subscribe("TRADE_EXECUTED", self._on_trade_executed)

    def _on_system_startup(self, data):
        send_telegram_msg("🚀 *[자동매매 서버 가동]*\n관제탑이 정상적으로 켜졌습니다.\n매일 아침 8시에 주도주 스캔 결과를 보고합니다.")

    def _on_scan_completed(self, data):
        targets = data.get("targets", [])
        if targets:
            msg = f"☀️ [아침 8시 스캔 완료]\n오늘 장중 집중 감시 및 사냥할 미너비니 주도주 TOP {len(targets)} 발굴 성공!\n\n"
            for rank, stock in enumerate(targets, 1):
                msg += f"{rank}위: {stock['Name']} ({stock['Symbol']}) - RS {stock['RS_Rating']:.1f}점\n"
            send_telegram_msg(msg)
        else:
            send_telegram_msg("☀️ [국내 아침 8시 스캔 정기보고]\n오늘 미너비니 7대 원칙을 뚫고 올라온 대장주가 없습니다. (관망 유지)")

    def _on_us_scan_completed(self, data):
        targets = data.get("targets", [])
        if targets:
            msg = f"🦅 [미국 아침 7시반 스캔 정기보고]\n오늘 밤 포획해야 할 S&P500 미너비니 주도주 TOP {len(targets)}!\n\n"
            for rank, stock in enumerate(targets, 1):
                msg += f"{rank}위: {stock['Name']} ({stock['Symbol']}) - RS {stock['RS_Rating']:.1f}점\n"
            send_telegram_msg(msg)
        else:
            send_telegram_msg("🦅 [미국 아침 7시반 스캔 정기보고]\n간밤에 통과한 S&P500 대장주가 없습니다.")

    def _on_scan_error(self, data):
        error = data.get("error", "알 수 없는 오류")
        send_telegram_msg(f"🚨 [아침 8시 스캔 실패]\n오류가 발생하여 스캔을 완료하지 못했습니다: {error}")

    def _on_trade_executed(self, data):
        trade_type = data.get("type")
        symbol = data.get("symbol")
        
        if trade_type == "CUT_LOSS":
            send_telegram_msg(f"🚨 *[손절 방어기제 발동]*\n{symbol} 종목이 손절 하한선(-8%) 이탈로 시장가 자동 투매되었습니다.\n위기 회피 성공.")
        elif trade_type == "BUY":
            price = data.get("price", 0)
            qty = data.get("qty", 0)
            held_count = data.get("held_count", 0)
            send_telegram_msg(f"🟢 *[매수 체결]*\n종목코드: {symbol}\n진입단가: {price:,}원\n수량: {qty}주\n누적 포트폴리오 차있는 개수: {held_count}개")
        elif trade_type == "SELL":
            qty = data.get("qty", 0)
            send_telegram_msg(f"🔴 *[전략 익절/매도 체결]*\n종목코드: {symbol}\n단기 하락 모멘텀 포착으로 싹 털어냅니다!\n투매 완료 수량: {qty}주")
