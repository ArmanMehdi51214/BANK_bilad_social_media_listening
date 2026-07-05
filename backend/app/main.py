import os
from app.modules.scheduler.router import router as scheduler_router
from app.modules.scheduler.jobs import register_scheduler_jobs
from app.modules.scheduler.manager import scheduler_manager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.modules.auth.router import router as auth_router
from app.modules.collection.router import router as collection_router
from app.modules.ai_analysis.router import router as ai_analysis_router
from app.modules.competitors.router import router as competitors_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.system.router import router as system_router


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.APP_DEBUG,
        version="0.1.0",
        description="Executive Social Media Intelligence Platform for Bank Albilad",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv(
                "BACKEND_CORS_ORIGINS",
                "http://localhost:3000,http://localhost:5173",
            ).split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(system_router, prefix=settings.API_V1_PREFIX)
    app.include_router(monitoring_router, prefix=settings.API_V1_PREFIX)
    app.include_router(competitors_router, prefix=settings.API_V1_PREFIX)

    app.include_router(
        collection_router,
        prefix=f"{settings.API_V1_PREFIX}/collection",
        tags=["Collection"],
    )

    return app


app = create_app()

app.include_router(ai_analysis_router, prefix=f"{settings.API_V1_PREFIX}/ai", tags=["AI Analysis"])


@app.on_event("startup")
def start_background_scheduler() -> None:
    register_scheduler_jobs(scheduler_manager)
    scheduler_manager.start()


@app.on_event("shutdown")
def stop_background_scheduler() -> None:
    scheduler_manager.stop(wait=False)

app.include_router(scheduler_router, prefix=f"{settings.API_V1_PREFIX}/scheduler", tags=["Scheduler"])
