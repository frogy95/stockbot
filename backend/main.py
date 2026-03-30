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

    yield

    # Shutdown
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

    return app


app = create_app()
