from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.redis import redis_client
from api.routes.health import router as health_router
from api.routes.settings import router as settings_router
from api.routes.kis import router as kis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    yield
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

    return app


app = create_app()
