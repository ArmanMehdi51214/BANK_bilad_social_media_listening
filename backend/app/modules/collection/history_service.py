from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.collection import CollectionJob, CollectionJobLog


class CollectionHistoryService:
    """
    Read-only service for collection job monitoring.

    Business purpose:
    Allows management/reporting users to audit collection runs and understand
    whether social media intelligence data is fresh, complete, or failing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_jobs(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[CollectionJob]]:
        query = self.db.query(CollectionJob)

        if platform:
            query = query.filter(CollectionJob.platform == platform)

        if status:
            query = query.filter(CollectionJob.status == status)

        total = query.count()

        jobs = (
            query.order_by(CollectionJob.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return total, jobs

    def get_job(self, job_id: UUID) -> Optional[CollectionJob]:
        return (
            self.db.query(CollectionJob)
            .filter(CollectionJob.id == job_id)
            .first()
        )

    def get_job_logs(self, job_id: UUID) -> list[CollectionJobLog]:
        return (
            self.db.query(CollectionJobLog)
            .filter(CollectionJobLog.collection_job_id == job_id)
            .order_by(CollectionJobLog.occurred_at.asc())
            .all()
        )
