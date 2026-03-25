import time
import requests
import threading
import logging
from core.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from notification.notifier import send_telegram_msg
from screening.screener_us import ScreenerUS
from screening.screener_kr import Screener

class TelegramBotManager:
    """
    [텔레그램 명령어 수신 매니저]
    백그라운드 스레드에서 텔레그램 서버를 Long Polling 방식으로 감시.
    검색 관련 기능은 누구나 사용할 수 있도록 Public 오픈 처리하며,
    HTS 기능(/portfolio, /stop)은 관리자만 사용할 수 있도록 분리합니다.
    """
    def __init__(self, event_bus=None):
        self.token = TELEGRAM_TOKEN
        self.allowed_chat_id = str(TELEGRAM_CHAT_ID)
        self.event_bus = event_bus
        self.last_update_id = 0
        self.is_running = False
        
        if self.event_bus:
            self.event_bus.subscribe("PORTFOLIO_REPORT", self._on_portfolio_report)
            self.event_bus.subscribe("BOT_STATE_CHANGED", self._on_bot_state_changed)
            
        # 스캐너를 명령어 수신때마다 재생성하지 않고, 하나씩만 유지하여 내부 캐시(Cache)를 공용으로 활용합니다.
        self.screener_kr = Screener()
        self.screener_us = ScreenerUS()
        
    def start_polling(self):
        if not self.token or "여기에" in self.token:
            logging.warning("[TelegramBot] 토큰이 없어 텔레그램 명령어 수신을 시작하지 않습니다.")
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._poll_updates, daemon=True)
        self.thread.start()
        logging.info("[TelegramBot] 백그라운드 명령어 수신(Polling) 스레드 가동 완료. (검색기능 Public 개방)")
        
    def stop_polling(self):
        self.is_running = False
        
    def _poll_updates(self):
        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {
                    "offset": self.last_update_id + 1,
                    "timeout": 10,
                    "allowed_updates": ["message"]
                }
                res = requests.get(url, params=params, timeout=12)
                res.raise_for_status()
                data = res.json()
                
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        self.last_update_id = update["update_id"]
                        message = update.get("message", {})
                        if message:
                            self._handle_message(message)
            except Exception:
                pass
            time.sleep(1)

    def _handle_message(self, message):
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()
        
        # [관리자 전용 HTS 기능 필터링]
        admin_commands = ["/portfolio", "/stop", "/resume"]
        is_admin = any(text.startswith(cmd) for cmd in admin_commands)
        
        if is_admin and chat_id != self.allowed_chat_id:
            logging.warning(f"[보안 차단] 외부인(Chat ID: {chat_id})이 권한 없는 관리자 명령어('{text}') 접근 시도")
            send_telegram_msg("⛔ **[보안 차단]** 해당 명령어는 관리자의 계좌와 직결되는 기능으로, 타인의 접근이 차단되었습니다.", chat_id=chat_id)
            return
            
        if text.startswith("/start"):
            self._reply_start(chat_id)
        elif text.startswith("/help"):
            self._reply_help(chat_id)
        elif text.startswith("/rs") or text.upper() == "RS":
            self._reply_rs(chat_id)
        elif text.startswith("/status"):
            self._reply_status(chat_id)
        elif text.startswith("/scan_kr"):
            self._reply_scan_kr(chat_id)
        elif text.startswith("/scan_us"):
            self._reply_scan_us(chat_id)
        elif text.startswith("/portfolio"):
            self._reply_portfolio()
        elif text.startswith("/stop"):
            self._reply_stop()
        elif text.startswith("/resume"):
            self._reply_resume()
        elif text.startswith("/"):
            send_telegram_msg("🤷 알 수 없는 명령어입니다. `/help`를 입력하여 사용법을 확인해보세요.", chat_id=chat_id)

    def _reply_start(self, chat_id):
        msg = (
            "🤖 *하이브리드 주도주 종목검색 봇*입니다!\n\n"
            "일반 사용자도 전 세계 누구나 주도주 스캔 기능을 이용할 수 있게 오픈되었습니다.\n"
            "봇의 전체 사용법을 보려면 `/help` 명령어를 입력해주세요!"
        )
        send_telegram_msg(msg, chat_id=chat_id)

    def _reply_help(self, chat_id):
        msg = (
            "💡 *[공용 명령어 도움말]*\n\n"
            "🔹 `/rs` - RS스코어(상대강도) 전략의 개념 및 필터 조건 템플릿 확인\n"
            "🔹 `/status` - 봇의 현재 상태 확인 및 생존 신고\n"
            "🔹 `/scan_kr` - 🇰🇷 국내장 코스피/코스닥 주도주 10선 실시간 발굴\n"
            "🔹 `/scan_us` - 🇺🇸 미국 S&P500 대상 주도주 10선 실시간 발굴\n\n"
            "🔒 *[관리자 전용 명령어]*\n"
            "🔹 `/portfolio` - 실시간 내 계좌 요약 보고 (외부인 차단)\n"
            "🔹 `/stop` & `/resume` - 엔진 일시정지 제어 스위치 (외부인 차단)\n\n"
            "궁금한 사항이 있다면 언제든 명령어를 호출해주세요!"
        )
        send_telegram_msg(msg, chat_id=chat_id)

    def _reply_rs(self, chat_id):
        msg = (
            "📈 *RS(Relative Strength) 스코어 & 미너비니 조건*\n\n"
            "▫️ *RS 스코어란?*\n"
            "최근 1년 동안 다른 주식 대비 해당 주식이 얼마나 강한 퍼포먼스를 보였는지를 1~99분위로 나타낸 지표입니다.\n"
            "본 봇은 가장 최근 3개월 성과에 40%의 무거운 가중치를 주어 99점에 가까운 '초강세 주도주'만 색출해냅니다.\n\n"
            "▫️ *미너비니 7대 템플릿 필터*\n"
            "1. 주가는 150일, 200일 이평선 위에 있다\n"
            "2. 150일선 > 200일선 (정배열 형태)\n"
            "3. 200일선 자체가 상승 중\n"
            "4. 50일선 > 150/200일선\n"
            "5. 현재 주가가 50일선보다 위에 위치\n"
            "6. 주가가 52주 신저가 대비 30% 이상 상승\n"
            "7. 주가가 52주 신고가의 25% 이내 최상단에 근접"
        )
        send_telegram_msg(msg, chat_id=chat_id)

    def _reply_status(self, chat_id):
        msg = "✅ *[봇 생존 신고]*\n현재 관제탑과 알림 봇이 퍼블릭 모드로 정상 가동 중입니다."
        send_telegram_msg(msg, chat_id=chat_id)

    def _reply_scan_kr(self, chat_id):
        send_telegram_msg("🇰🇷 *[국내장 주도주 스캔 작동]*\n코스피/코스닥 대장주 발굴 스캔을 요청했습니다. (오늘자 첫 스캔일 경우 데이터 수집에 약 5분이 소요되며, 이미 오늘 누군가 스캔을 시켰다면 캐시에서 1초 만에 반환됩니다.)", chat_id=chat_id)
        
        def run_kr_scan():
            targets = self.screener_kr.run_daily_scan(top_n=10)
            if targets:
                msg = f"🐯 [국내장 주도주 스캔 완료]\n한국 증시 중 미너비니 요건을 통과한 TOP {len(targets)} 주도주!\n\n"
                for rank, stock in enumerate(targets, 1):
                    msg += f"{rank}위: {stock['Name']} ({stock['Symbol']}) - RS {stock['RS_Rating']:.1f}점\n"
                send_telegram_msg(msg, chat_id=chat_id)
            else:
                send_telegram_msg("🐯 [국내장 스캔 완료]\n오늘 엄청난 하락장이었나요? 한국 증시 중 미너비니 7대 원칙을 통과한 대장주가 0개입니다.", chat_id=chat_id)
                
        threading.Thread(target=run_kr_scan, daemon=True).start()

    def _reply_scan_us(self, chat_id):
        send_telegram_msg("🇺🇸 *[미국장 주도주 스캔 작동]*\n미국 S&P500 대장주 발굴 스캔을 요청했습니다. (오늘자 첫 스캔일 경우 데이터 수집에 약 5분이 소요되며, 이미 성공적으로 스캔되었다면 1초 내로 결괏값이 메아리칩니다.)", chat_id=chat_id)
        
        def run_us_scan():
            targets = self.screener_us.run_daily_scan(top_n=10)
            if targets:
                msg = f"🦅 [미국장 주도주 스캔 완료]\nS&P500 중 미너비니 요건을 통과한 TOP {len(targets)} 주도주!\n\n"
                for rank, stock in enumerate(targets, 1):
                    msg += f"{rank}위: {stock['Name']} ({stock['Symbol']}) - RS {stock['RS_Rating']:.1f}점\n"
                send_telegram_msg(msg, chat_id=chat_id)
            else:
                send_telegram_msg("🦅 [미국장 스캔 완료]\n오늘 엄청난 하락장이었나요? S&P500 중 미너비니 7대 원칙을 통과한 대장주가 0개입니다.", chat_id=chat_id)
                
        threading.Thread(target=run_us_scan, daemon=True).start()

    # ------------------ 관리자(본인) 전용 이벤트 콜백 ------------------
    # 관리자는 무조건 config.py 의 allowed_chat_id 이므로 매개변수를 쓰지 않아도 됩니다.
    def _reply_portfolio(self):
        send_telegram_msg("🔄 HTS 연동: 계좌 정보를 실시간 조회 중입니다...")
        if self.event_bus: self.event_bus.publish("REQUEST_PORTFOLIO")

    def _reply_stop(self):
        send_telegram_msg("🛑 관제탑 매매 감시망 가동 중단(Sleep)을 지시했습니다.")
        if self.event_bus: self.event_bus.publish("CMD_STOP")

    def _reply_resume(self):
        send_telegram_msg("▶️ 관제탑 매매 감시망 가동 재개를 지시했습니다.")
        if self.event_bus: self.event_bus.publish("CMD_RESUME")

    def _on_portfolio_report(self, data):
        if "error" in data:
            send_telegram_msg(f"❌ 포트폴리오 조회 실패:\n{data['error']}")
            return
            
        msg = f"📊 *[계좌 포트폴리오 실시간 현황]*\n"
        msg += f"💰 총 자산: {data.get('total_cash', 0):,}원\n"
        msg += f"💵 예수금: {data.get('available_buy', 0):,}원\n"
        holdings = data.get('holdings', [])
        msg += f"📦 보유 종목 수: {len(holdings)}개\n\n"
        for h in holdings:
            symbol = h.get('pdno', '')
            qty = h.get('hldg_qty', 0)
            profit_rate = h.get('evlu_erng_rt', 0)
            profit_amt = h.get('evlu_pfls_amt', 0)
            msg += f"▫️ {symbol} : {qty}주 (수익률 {profit_rate}% / 손익 {profit_amt}원)\n"
        send_telegram_msg(msg)

    def _on_bot_state_changed(self, data):
        state = "일시정지(Sleep) 💤" if data.get("is_paused") else "가동 중(Active) 🔥"
        send_telegram_msg(f"⚙️ 변경: 관제탑은 *{state}* 상태입니다.")
