import logging
import datetime
import pandas as pd
import os

from data.kis_api import KoreaInvestmentAPI
from data.data_manager import DataManager
from screening.screener_kr import Screener
from screening.screener_us import ScreenerUS
from trading.strategy import HybridMomentumStrategy
from trading.portfolio import PortfolioManager
from core.event_bus import EventBus
from notification.notifier import NotificationService
from notification.telegram_bot import TelegramBotManager

class BotEngine:
    """
    [하이브리드 메인 관제탑 엔진]
    시스템의 모든 OOP 모듈(API, Data, Screener, Strategy, Portfolio)의 생명주기와
    통신(EventBus)을 조율하는 중앙 컨트롤러입니다.
    """
    def __init__(self, 
                 event_bus: EventBus, 
                 api: KoreaInvestmentAPI, 
                 data_manager: DataManager, 
                 screener_kr: Screener, 
                 screener_us: ScreenerUS, 
                 strategy: HybridMomentumStrategy, 
                 portfolio: PortfolioManager,
                 telegram_bot: TelegramBotManager):
        
        self.is_paused = False  # 자동 매매 일시정지 제어 플래그
        self.is_running = False # 시스템 엔진 가동 상태 플래그

        # 의존성 주입 (Dependency Injection)
        self.event_bus = event_bus
        self.notifier = NotificationService(self.event_bus) # Notifier는 엔진과 강결합된 유틸리티로 취급
        self.api = api
        self.data_manager = data_manager
        self.screener = screener_kr
        self.screener_us = screener_us
        self.strategy = strategy
        self.portfolio = portfolio
        self.telegram_bot = telegram_bot

    def start(self):
        """
        [엔진 가동]
        이벤트 구독을 활성화하고 텔레그램 폴링 등 백그라운드 서비스를 시작합니다.
        """
        if self.is_running:
            logging.warning("[BotEngine] 엔진이 이미 실행 중입니다.")
            return

        logging.info("[BotEngine] 시스템 부팅 및 이벤트 와이어링 시작...")
        
        try:
            # 1. 이벤트 구독 등록 (Wiring)
            self.event_bus.subscribe("REQUEST_PORTFOLIO", self._handle_request_portfolio)
            self.event_bus.subscribe("MANUAL_BUY", self._handle_manual_buy)
            self.event_bus.subscribe("CMD_STOP", self._handle_cmd_stop)
            self.event_bus.subscribe("CMD_RESUME", self._handle_cmd_resume)
            
            # 2. 텔레그램 명령어 수신 시작
            if self.telegram_bot:
                self.telegram_bot.start_polling()
            
            self.is_running = True
            logging.info("[BotEngine] 🚀 하이브리드 자동매매 엔진이 정상적으로 가동되었습니다.")
            
        except Exception as e:
            logging.error(f"[BotEngine] 엔진 구동 중 치명적 오류 발생: {e}", exc_info=True)
            raise e # 상위 호출자(main.py)에게 오류 전달

    def stop(self):
        """[엔진 정지] 하위 서비스들을 안전하게 종료합니다."""
        logging.info("[BotEngine] 엔진 종료 절차를 시작합니다...")
        self.is_running = False
        # 필요한 경우 여기에 텔레그램 폴링 중지 로직 등을 추가할 수 있습니다.

        
    def run_us_scan(self):
        """매일 아침 07:30 에 예약되어 텔레그램 오픈 전에 방대한 S&P500 최신본을 수집 후 캐싱(보관)합니다."""
        logging.info("========== [주간 작업] 아침 07시 30분 미국 증시 자동 사전 스캐너 가동 ==========")
        try:
            targets_info = self.screener_us.run_daily_scan(top_n=10)
            if not targets_info:
                logging.info("-> 오늘 S&P500 중 미너비니 7대 원칙을 뚫고 올라온 대장주가 없습니다.")
            # 성공 유무 무관하게 시스템 텔레그램에 직통 알림 발송
            self.event_bus.publish("US_SCAN_COMPLETED", {"targets": targets_info})
        except Exception as e:
            logging.error(f"[BotEngine] 미국장 사전 스캔 중 오류: {e}")

    def run_morning_scan(self):
        """매일 아침 08:00에 동작하여 국내 상장 듀얼 트랙(대형주/성장주)을 사전 스캔합니다."""
        logging.info("========== [주간 작업] 아침 08시 듀얼 트랙 스캐너 가동 ==========")
        try:
            # 1. 대형 주도주 스캔 (Top 200)
            large_targets = self.screener.run_daily_scan(top_n=10, mode="LARGE")
            
            # 2. 중소형 성장주 스캔 (시총 1조 이하 + 거래대금 상위)
            growth_targets = self.screener.run_daily_scan(top_n=10, mode="GROWTH")
            
            # 통합 결과 (이벤트 전송용)
            combined_targets = large_targets + growth_targets
            self.event_bus.publish("SCAN_COMPLETED", {"targets": combined_targets})
                
        except Exception as e:
            logging.error(f"[BotEngine] 국내장 듀얼 스캔 중 오류: {e}")

            logging.error(f"[BotEngine] 아침 스캔 중 오류 발생: {e}")
            self.event_bus.publish("SCAN_ERROR", {"error": str(e)})

    def load_watchlist(self) -> list:
        """오늘 날짜의 모든 워치리스트(large/growth)를 통합하여 리스트를 반환합니다."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        modes = ["large", "growth"]
        combined_symbols = []
        
        for mode in modes:
            path = f"watchlists/watchlist_kr_{mode}_{today}.csv"
            if not os.path.exists(path):
                continue
            try:
                # KRX 종목번호 6자리 유지를 위해 zfill 처리
                df = pd.read_csv(path, encoding='utf-8-sig')
                symbols = df['Symbol'].astype(str).str.zfill(6).tolist()
                combined_symbols.extend(symbols)
            except Exception as e:
                logging.error(f"[BotEngine] 워치리스트 로드 실패 ({path}): {e}")
        
        # 중복 제거 (대형주이면서 성장주 조건에 걸릴 가능성 대비)
        return list(set(combined_symbols))


    def is_market_open(self) -> bool:
        """한국 주식 시장 평일 09:00 ~ 15:20 필터링"""
        now = datetime.datetime.now()
        if now.weekday() >= 5: return False
        start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end = now.replace(hour=15, minute=20, second=0, microsecond=0)
        return start <= now <= end

    def bot_job(self):
        """장중 정기(예: 30분 마다) 모니터링 사이클"""
        logging.info("=========== [장중 작업] 타점 모니터링 사이클 가동 ===========")
        
        if self.is_paused:
            logging.info("[대기] 텔레그램 원격 제어를 통해 엔진이 멈춰있습니다. 매매 루프를 건너뜁니다.")
            return
            
        if not self.api.access_token:
            logging.info("[대기] API 인증 토큰이 없습니다. 스캐닝 점검은 계속되나 자동매매는 비활성화됩니다.")
            return

        balance_info = self.api.get_account_balance()

        if not balance_info: return
            
        holdings = balance_info['holdings']
        available_cash = balance_info['available_buy']
        
        # 보유 주식의 현 평가금액을 더해 수동으로 내 계좌 총 자산을 추산 (목표 비중 계산용)
        stock_eval_amt = sum([int(h.get('evlu_amt', 0)) for h in holdings])
        total_equity = balance_info['total_cash'] + stock_eval_amt
        held_count = len(holdings)
        
        # ⭐️ 방금 전 스캐너가 저장해둔 타겟 리스트 (watchlist.csv) 로드 ⭐️
        targets = self.load_watchlist()
        if not targets:
            logging.info("발굴된 watchlist.csv 종목이 없어 신규 진입 매수 로직을 건너뜁니다.")
            
        # ----------------------------------------------------
        # 1. 최우선 감시: 포트폴리오(내 보유 종목들) 하드 손절매(-8%) 방어 기동
        # ----------------------------------------------------
        for stock in holdings:
            symbol = stock.get('pdno')
            avg_price = float(stock.get('pchs_avg_pric', 0))
            current_price = float(stock.get('prpr', 0))
            qty = int(stock.get('hldg_qty', 0))
            
            # 포트폴리오 객체에게 이 종목 손절쳐야 하는지 심사 요청
            is_stop_loss = self.portfolio.check_stop_loss(avg_price, current_price)
            if is_stop_loss and qty > 0:
                logging.warning(f"[강제 손절 집행] {symbol} 종목이 -8% 선을 박살냈습니다. 시장가 전량 투매.")
                success, _ = self.api.place_order(symbol, is_buy=False, qty=qty, prc="0", ord_type="01")
                if success:
                    self.event_bus.publish("TRADE_EXECUTED", {"type": "CUT_LOSS", "symbol": symbol})
                continue # 다음 코인으로 넘어감, 단기 전략 검사 생략
                
        # ----------------------------------------------------
        # 2. 미너비니 뚫고 올라온 타겟 차트 단기 모멘텀 타점 추적
        # ----------------------------------------------------
        for symbol in targets:
            # 일봉 100일치를 가져와서 단기 박스권이나 추세 꺾임/진입 판단
            df_raw = self.data_manager.get_historical_data(symbol, period="D")
            df_analyzed = self.data_manager.add_indicators(df_raw)
            if df_raw.empty: continue
            
            # Hybrid 전략체에 인계하여 BUY/SELL 타점인지 점검
            signal = self.strategy.get_signal(df_analyzed)
            current_price = int(df_raw.iloc[-1]['Close'])
            
            # 이미 계좌에 담긴 상태라면 중복 진입 회피 (분할매수 전용 아닐 때)
            already_held = any(sym['pdno'] == symbol for sym in holdings)
            
            if signal == "BUY" and not already_held:
                logging.info(f"[{symbol}] 모멘텀 반등 단기 타점 적중! (현재가: {current_price:,}원)")
                
                # 포트폴리오 객체에게 '자산 분배 관점에 따르면 이놈 몇 주 사야 안전해?' 묻습니다.
                buy_qty = self.portfolio.allocate_capital(available_cash, total_equity, current_price, held_count)
                
                if buy_qty > 0:
                    logging.info(f"-> (금액: {buy_qty*current_price:,}원) 포폴 비중 승인됨. 매수 진입합니다.")
                    success, _ = self.api.place_order(symbol, is_buy=True, qty=buy_qty, prc="0", ord_type="01")
                    if success:
                        available_cash -= (buy_qty * current_price) # 가상 현금 차감(동시 매수 돈 초과 방지)
                        held_count += 1 
                        self.event_bus.publish("TRADE_EXECUTED", {"type": "BUY", "symbol": symbol, "price": current_price, "qty": buy_qty, "held_count": held_count})
                else:
                    logging.info("-> 비중 할당 반려됨 (잔고 부족이거나 이미 최대 5종목 포트폴리오 꽉 참)")
                    
            elif signal == "SELL" and already_held:
                # 손절(-8)은 안 났지만 단기 모멘텀 매도(예: MACD 데크 + RSI 고점) 시그널일 때 익절/손절 청산
                target_held_info = next((item for item in holdings if item["pdno"] == symbol), None)
                if target_held_info:
                    qty = int(target_held_info.get('hldg_qty', 0))
                    logging.info(f"[{symbol}] 하이브리드 단기 상승 모멘텀 소멸 감지. 즉시 전량({qty}주) 시장가 매도.")
                    success, _ = self.api.place_order(symbol, is_buy=False, qty=qty, prc="0", ord_type="01")
                    if success:
                        self.event_bus.publish("TRADE_EXECUTED", {"type": "SELL", "symbol": symbol, "qty": qty})

    # ==============================================================================
    # 텔레그램 연동 HTS/MTS 제어 이벤트 핸들러 모음
    # ==============================================================================
    def _handle_request_portfolio(self, data):
        try:
            balance = self.api.get_account_balance()
            if balance:
                self.event_bus.publish("PORTFOLIO_REPORT", balance)
            else:
                self.event_bus.publish("PORTFOLIO_REPORT", {"error": "API 키 오류 혹은 증권사 서버 응답 불가"})
        except Exception as e:
            logging.error(f"[BotEngine] 포트폴리오 조회 에러: {e}")
            self.event_bus.publish("PORTFOLIO_REPORT", {"error": str(e)})

    def _handle_manual_buy(self, data):
        symbol = data.get("symbol")
        if not symbol: return
        
        if not self.api.access_token:
            self.event_bus.publish("MANUAL_BUY_RESULT", {"success": False, "symbol": symbol, "reason": "API 인증 키가 설정되지 않았습니다. .env 파일을 확인해 주세요."})
            return
            
        try:
            balance = self.api.get_account_balance()

            if not balance:
                self.event_bus.publish("MANUAL_BUY_RESULT", {"success": False, "symbol": symbol, "reason": "API 잔고 조회 불가"})
                return
            
            df = self.data_manager.get_historical_data(symbol, period="D")
            if df.empty:
                self.event_bus.publish("MANUAL_BUY_RESULT", {"success": False, "symbol": symbol, "reason": "유효하지 않은 종목코드 또는 데이터 없음"})
                return
            
            current_price = int(df.iloc[-1]['Close'])
            stock_eval_amt = sum([int(h.get('evlu_amt', 0)) for h in balance['holdings']])
            total_equity = balance['total_cash'] + stock_eval_amt
            held_count = len(balance['holdings'])
            available_cash = balance['available_buy']
            
            buy_qty = self.portfolio.allocate_capital(available_cash, total_equity, current_price, held_count)
            
            if buy_qty > 0:
                logging.info(f"[수동 지시] {symbol} {buy_qty}주 시장가 매수 시도")
                # 테스트 모의투자 API 특성상 억지 체결될 수 있으므로, 에러 코드는 API 안에서 던집니다.
                success, reason_info = self.api.place_order(symbol, is_buy=True, qty=buy_qty, prc="0", ord_type="01")
                
                # 매수 성공 시 자동매매 루틴과 동일하게 체결 보고를 위해 TRADE 형식으로도 하나 던집니다.
                if success:
                    self.event_bus.publish("TRADE_EXECUTED", {
                        "type": "BUY", "symbol": symbol, "price": current_price, "qty": buy_qty, "held_count": held_count + 1
                    })
                
                # 수동 매수 액션 자체에 대한 결과 (성공, 실패이유 등) 응답
                self.event_bus.publish("MANUAL_BUY_RESULT", {"success": success, "symbol": symbol, "reason": reason_info})
            else:
                reason = "최대 5종목 포트폴리오 초과, 비중 제한, 또는 예수금 부족"
                logging.warning(f"[수동 지시 반려] {symbol}: {reason}")
                self.event_bus.publish("MANUAL_BUY_RESULT", {"success": False, "symbol": symbol, "reason": reason})
                
        except Exception as e:
            logging.error(f"[BotEngine] 수동 매수 에러: {e}")
            self.event_bus.publish("MANUAL_BUY_RESULT", {"success": False, "symbol": symbol, "reason": str(e)})

    def _handle_cmd_stop(self, data):
        self.is_paused = True
        logging.info("[BotEngine] 텔레그램 명령으로 인해 자동매매 엔진 가동이 일시 중지되었습니다.")
        self.event_bus.publish("BOT_STATE_CHANGED", {"is_paused": True})

    def _handle_cmd_resume(self, data):
        self.is_paused = False
        logging.info("[BotEngine] 텔레그램 명령으로 인해 자동매매 엔진 가동이 재개되었습니다.")
        self.event_bus.publish("BOT_STATE_CHANGED", {"is_paused": False})
