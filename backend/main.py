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
from api.routes.health import router as health_router
from api.routes.settings import router as settings_router
from api.routes.kis import router as kis_router
from api.routes.collector import router as collector_router

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

    yield

    # Shutdown
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

    return app


app = create_app()
