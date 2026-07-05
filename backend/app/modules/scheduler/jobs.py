from __future__ import annotations

import asyncio
import inspect
import os
import re
import threading
from datetime import datetime
from typing import Any
from uuid import uuid4

from loguru import logger

from app.db.session import SessionLocal
from app.modules.collection.service import XCollectionService
from app.modules.ai_analysis.pipeline_runner import run_ai_pipeline_for_unprocessed


_COLLECTION_LOCK = threading.Lock()

_RUNTIME_STATE: dict[str, Any] = {
    "is_running": False,
    "active_run_id": None,
    "last_started_at": None,
    "last_finished_at": None,
    "last_status": None,
    "last_error": None,
    "last_result": None,
    "run_count": 0,
    "skipped_overlap_count": 0,
}


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _redact_secret(value: str) -> str:
    value = re.sub(r"token=[^&\s]+", "token=[REDACTED]", value)
    value = re.sub(r"apify_api_[A-Za-z0-9]+", "apify_api_[REDACTED]", value)
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    if not isinstance(value, (str, int, float, bool, type(None))):
        return str(value)

    return value


def _resolve_maybe_async(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def get_scheduler_runtime_state() -> dict[str, Any]:
    return _json_safe(dict(_RUNTIME_STATE))


def run_scheduled_x_collection() -> dict[str, Any]:
    """
    Safe scheduled X collection job.

    Protection:
    - Prevents overlapping scheduled/manual runs
    - Tracks active run status
    - Returns clean JSON-safe result
    """

    lock_acquired = _COLLECTION_LOCK.acquire(blocking=False)

    if not lock_acquired:
        _RUNTIME_STATE["skipped_overlap_count"] += 1

        logger.warning(
            "Scheduled X collection skipped because another run is already active | active_run_id={}",
            _RUNTIME_STATE.get("active_run_id"),
        )

        return {
            "status": "skipped",
            "reason": "collection_already_running",
            "active_run_id": _RUNTIME_STATE.get("active_run_id"),
            "runtime_state": get_scheduler_runtime_state(),
        }

    run_id = str(uuid4())
    max_items = int(os.getenv("SCHEDULER_X_MAX_ITEMS", "10"))
    sort = os.getenv("SCHEDULER_X_SORT", "Latest")

    _RUNTIME_STATE["is_running"] = True
    _RUNTIME_STATE["active_run_id"] = run_id
    _RUNTIME_STATE["last_started_at"] = _utc_now_iso()
    _RUNTIME_STATE["last_finished_at"] = None
    _RUNTIME_STATE["last_status"] = "running"
    _RUNTIME_STATE["last_error"] = None

    db = SessionLocal()

    try:
        logger.info(
            "Scheduled X collection started | run_id={} | max_items={} | sort={}",
            run_id,
            max_items,
            sort,
        )

        service = XCollectionService(db)

        result = service.collect_active_rules(
            max_items=max_items,
            sort=sort,
            target_types=None,
            rule_ids=None,
        )

        result = _resolve_maybe_async(result)
        result = _json_safe(result)

        ai_pipeline_result = None

        if os.getenv("SCHEDULER_RUN_AI_AFTER_COLLECTION", "true").lower() == "true":
            if isinstance(result, dict) and result.get("status") == "success":
                ai_limit = int(os.getenv("SCHEDULER_AI_MAX_ITEMS", "500"))
                ai_pipeline_result = run_ai_pipeline_for_unprocessed(
                    db=db,
                    platform="x",
                    limit=ai_limit,
                    dry_run=False,
                )

        response = {
            "status": "completed",
            "run_id": run_id,
            "max_items": max_items,
            "sort": sort,
            "result": result,
            "ai_pipeline": ai_pipeline_result,
        }

        _RUNTIME_STATE["last_status"] = "completed"
        _RUNTIME_STATE["last_result"] = response
        _RUNTIME_STATE["run_count"] += 1

        logger.info(
            "Scheduled X collection completed | run_id={} | result={}",
            run_id,
            result,
        )

        return response

    except Exception as exc:
        error_message = _redact_secret(str(exc))

        response = {
            "status": "failed",
            "run_id": run_id,
            "error": error_message,
        }

        _RUNTIME_STATE["last_status"] = "failed"
        _RUNTIME_STATE["last_error"] = error_message
        _RUNTIME_STATE["last_result"] = response

        logger.error(
            "Scheduled X collection failed | run_id={} | error={}",
            run_id,
            error_message,
        )

        return response

    finally:
        db.close()

        _RUNTIME_STATE["is_running"] = False
        _RUNTIME_STATE["active_run_id"] = None
        _RUNTIME_STATE["last_finished_at"] = _utc_now_iso()

        _COLLECTION_LOCK.release()


def register_scheduler_jobs(scheduler_manager) -> None:
    """
    Registers scheduled background jobs.
    """
    x_enabled = os.getenv("SCHEDULER_X_COLLECTION_ENABLED", "true").lower() == "true"

    if not x_enabled:
        logger.warning("Scheduled X collection disabled by SCHEDULER_X_COLLECTION_ENABLED=false")
        return

    interval_minutes = int(os.getenv("SCHEDULER_X_INTERVAL_MINUTES", "60"))

    scheduler_manager.add_interval_job(
        job_id="scheduled_x_collection",
        name="Scheduled X Collection",
        func=run_scheduled_x_collection,
        minutes=interval_minutes,
        replace_existing=True,
        max_instances=1,
    )
