from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.router import router as auth_router
from app.modules.system.router import router as system_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.competitors.router import router as competitors_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(system_router)
api_router.include_router(monitoring_router)
api_router.include_router(competitors_router)


@api_router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "Bank Albilad Executive Social Media Intelligence API",
        "version": "0.1.0",
    }


@api_router.get("/db-health", tags=["System"])
def database_health_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1 AS status")).scalar()

    return {
        "status": "healthy" if result == 1 else "unhealthy",
        "database": "PostgreSQL",
        "connected": result == 1,
    }
