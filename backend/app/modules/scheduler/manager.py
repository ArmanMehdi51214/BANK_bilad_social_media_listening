from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger


class SchedulerManager:
    def __init__(self) -> None:
        self.timezone = os.getenv("SCHEDULER_TIMEZONE", "Asia/Riyadh")
        self.enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
        self.scheduler = self._build_scheduler()
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None

    def _build_scheduler(self) -> BackgroundScheduler:
        return BackgroundScheduler(
            timezone=self.timezone,
            daemon=True,
        )

    def start(self) -> bool:
        if not self.enabled:
            logger.warning("Scheduler is disabled by SCHEDULER_ENABLED=false")
            return False

        if self.scheduler.running:
            logger.info("Scheduler already running")
            return True

        try:
            self.scheduler.start()
        except RuntimeError:
            self.scheduler = self._build_scheduler()
            self.scheduler.start()

        self.started_at = datetime.utcnow()
        self.stopped_at = None

        logger.info(
            "Scheduler started | timezone={} | started_at={}",
            self.timezone,
            self.started_at.isoformat(),
        )

        return True

    def stop(self, wait: bool = False) -> bool:
        if not self.scheduler.running:
            logger.info("Scheduler already stopped")
            return True

        self.scheduler.shutdown(wait=wait)
        self.stopped_at = datetime.utcnow()
        self.started_at = None
        self.scheduler = self._build_scheduler()

        logger.info(
            "Scheduler stopped | stopped_at={}",
            self.stopped_at.isoformat(),
        )

        return True

    def status(self) -> dict[str, Any]:
        jobs = []

        for job in self.scheduler.get_jobs():
            try:
                next_run_time = getattr(job, "next_run_time", None)
            except AttributeError:
                next_run_time = None

            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": next_run_time.isoformat()
                    if next_run_time
                    else None,
                    "trigger": str(job.trigger),
                }
            )

        return {
            "enabled": self.enabled,
            "running": self.scheduler.running,
            "timezone": self.timezone,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "job_count": len(jobs),
            "jobs": jobs,
        }

    def add_interval_job(
        self,
        *,
        job_id: str,
        name: str,
        func,
        minutes: int,
        replace_existing: bool = True,
        max_instances: int = 1,
    ) -> None:
        self.scheduler.add_job(
            func=func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            name=name,
            replace_existing=replace_existing,
            max_instances=max_instances,
            coalesce=True,
            misfire_grace_time=300,
        )

        logger.info(
            "Scheduler job registered | job_id={} | name={} | minutes={}",
            job_id,
            name,
            minutes,
        )


scheduler_manager = SchedulerManager()
