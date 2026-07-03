import sys
from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()

    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        enqueue=True,
        backtrace=settings.APP_DEBUG,
        diagnose=settings.APP_DEBUG,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
    )

    logger.add(
        "storage/logs/app.log",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        level=settings.LOG_LEVEL,
        enqueue=True,
    )
