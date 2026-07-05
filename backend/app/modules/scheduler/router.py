from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.collection.dependencies import require_collection_operator
from app.modules.scheduler.jobs import (
    register_scheduler_jobs,
    run_scheduled_x_collection,
    get_scheduler_runtime_state,
)
from app.modules.scheduler.manager import scheduler_manager


router = APIRouter()


@router.get("/status")
def get_scheduler_status(
    _current_user=Depends(require_collection_operator),
):
    status = scheduler_manager.status()
    status["runtime_state"] = get_scheduler_runtime_state()
    return status


@router.post("/start")
def start_scheduler(
    _current_user=Depends(require_collection_operator),
):
    register_scheduler_jobs(scheduler_manager)
    started = scheduler_manager.start()

    return {
        "started": started,
        "status": {
            **scheduler_manager.status(),
            "runtime_state": get_scheduler_runtime_state(),
        },
    }


@router.post("/stop")
def stop_scheduler(
    _current_user=Depends(require_collection_operator),
):
    stopped = scheduler_manager.stop(wait=False)

    return {
        "stopped": stopped,
        "status": {
            **scheduler_manager.status(),
            "runtime_state": get_scheduler_runtime_state(),
        },
    }


@router.post("/run-now")
def run_scheduler_now(
    _current_user=Depends(require_collection_operator),
):
    result = run_scheduled_x_collection()

    return {
        "job_id": "scheduled_x_collection",
        "result": result,
        "scheduler_status": {
            **scheduler_manager.status(),
            "runtime_state": get_scheduler_runtime_state(),
        },
    }
