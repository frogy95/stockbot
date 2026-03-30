import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.redis import redis_client
from core.clients.kis_config import get_current_environment
from core.clients.token_manager import KISTokenManager
from core.clients.throttler import TokenBucketThrottler
from core.clients.kis_rest import KISRestClient
from core.clients.kis_ws import KISWebSocketClient
from core.database import get_session_factory
from modules.collector.ws_manager import WSSubscriptionManager
from modules.collector.trade_strength import TradeStrengthCalculator
from modules.collector.scheduler import CollectorScheduler
from api.routes.health import router as health_router
from api.routes.settings import router as settings_router
from api.routes.kis import router as kis_router
from api.routes.collector import router as collector_router
from api.routes.screening import router as screening_router
from modules.screening.screener import PrimaryScreener
from modules.screening.realtime_screener import RealtimeScreener
from modules.trading.risk_manager import RiskManager
from modules.trading.position_sizer import PositionSizer
from modules.trading.eod_liquidator import EodLiquidator
from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy
from modules.trading.signal_generator import SignalGenerator
from modules.trading.order_manager import OrderManager
from modules.trading.position_manager import PositionManager
from modules.trading.engine import TradingEngine
from api.routes.trading import router as trading_router
from api.routes.telegram import router as telegram_router
from modules.notifier.approval import ApprovalManager
from modules.notifier.telegram_bot import TelegramBot
from modules.notifier.manager import NotifierManager
from modules.notifier.commands import CommandHandler
from core.config import settings as app_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Redis
    await redis_client.connect()

    # KIS 클라이언트 초기화
    env = get_current_environment()
    token_manager = KISTokenManager(env=env, redis=redis_client)
    throttler = TokenBucketThrottler(interval=env.rate_limit_interval)
    rest_client = KISRestClient(env=env, token_manager=token_manager, throttler=throttler)
    ws_client = KISWebSocketClient(env=env, token_manager=token_manager)

    app.state.kis_env = env
    app.state.kis_token_manager = token_manager
    app.state.kis_throttler = throttler
    app.state.kis_rest = rest_client
    app.state.kis_ws = ws_client

    logger.info("KIS 클라이언트 초기화 완료 (환경: %s)", env.name)

    # 수집 모듈 초기화
    session_factory = get_session_factory()
    trade_strength = TradeStrengthCalculator()
    ws_manager = WSSubscriptionManager(ws_client)

    # 스크리닝 모듈 초기화
    primary_screener = PrimaryScreener()
    realtime_screener = RealtimeScreener(
        redis_client=redis_client,
        trade_strength_calc=trade_strength,
    )

    collector_scheduler = CollectorScheduler(
        session_factory=session_factory,
        rest_client=rest_client,
        ws_manager=ws_manager,
        trade_strength=trade_strength,
        ws_client=ws_client,
        redis=redis_client,
        primary_screener=primary_screener,
        realtime_screener=realtime_screener,
    )

    app.state.trade_strength = trade_strength
    app.state.ws_manager = ws_manager
    app.state.primary_screener = primary_screener
    app.state.realtime_screener = realtime_screener
    app.state.collector_scheduler = collector_scheduler

    await collector_scheduler.start()
    logger.info("수집 스케줄러 초기화 완료")

    # 매매 모듈 초기화
    risk_manager = RiskManager(session_factory, redis_client)
    await risk_manager.load_settings()
    position_sizer = PositionSizer(session_factory)
    await position_sizer.load_settings()
    eod_liquidator = EodLiquidator(session_factory, rest_client, redis_client)
    await eod_liquidator.check_and_liquidate_on_startup()
    await eod_liquidator.register_schedule(collector_scheduler._scheduler)

    app.state.risk_manager = risk_manager
    app.state.position_sizer = position_sizer
    app.state.eod_liquidator = eod_liquidator
    logger.info("매매 모듈 초기화 완료 (리스크 매니저, 포지션 사이저, 당일 청산)")

    # 알림 모듈 초기화
    notifier_manager = None
    if app_settings.TELEGRAM_BOT_TOKEN and app_settings.TELEGRAM_CHAT_ID:
        approval_manager = ApprovalManager(redis_client)
        telegram_bot = TelegramBot(
            app_settings.TELEGRAM_BOT_TOKEN,
            app_settings.TELEGRAM_CHAT_ID,
            approval_manager,
        )
        notifier_manager = NotifierManager(telegram_bot, approval_manager, session_factory)
        app.state.approval_manager = approval_manager
        app.state.telegram_bot = telegram_bot
        app.state.notifier_manager = notifier_manager
        command_handler = CommandHandler(session_factory, redis_client, telegram_bot)
        app.state.command_handler = command_handler
        logger.info("텔레그램 알림 모듈 초기화 완료")

    # 매매 엔진 초기화
    strategy = MomentumBreakoutStrategy()
    signal_generator = SignalGenerator(session_factory, redis_client, strategy)
    order_manager = OrderManager(session_factory, rest_client, redis_client, throttler)
    position_manager = PositionManager(session_factory, redis_client, risk_manager)
    trading_engine = TradingEngine(
        signal_generator=signal_generator,
        order_manager=order_manager,
        position_manager=position_manager,
        risk_manager=risk_manager,
        position_sizer=position_sizer,
        eod_liquidator=eod_liquidator,
        redis_client=redis_client,
        notifier_manager=notifier_manager,
    )
    await trading_engine.start()
    app.state.trading_engine = trading_engine
    logger.info("매매 엔진 초기화 완료")

    # 텔레그램 웹훅 설정
    if notifier_manager and app_settings.TELEGRAM_WEBHOOK_URL:
        webhook_url = app_settings.TELEGRAM_WEBHOOK_URL + "/api/v1/telegram/webhook"
        await telegram_bot.set_webhook(webhook_url)
        logger.info("텔레그램 웹훅 설정: %s", webhook_url)

    yield

    # Shutdown
    if notifier_manager and app_settings.TELEGRAM_WEBHOOK_URL:
        await telegram_bot.delete_webhook()
    await trading_engine.stop()
    await collector_scheduler.stop()
    await rest_client.close()
    await ws_client.disconnect()
    await token_manager.close()
    await redis_client.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="StockBot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(kis_router, prefix="/api/v1")
    app.include_router(collector_router, prefix="/api/v1")
    app.include_router(screening_router, prefix="/api/v1")
    app.include_router(trading_router, prefix="/api/v1")
    app.include_router(telegram_router, prefix="/api/v1")

    return app


app = create_app()
