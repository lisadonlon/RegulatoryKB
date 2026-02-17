"""
Health check endpoint for monitoring service status.
"""

from datetime import datetime

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    """Return service health status as JSON."""
    started_at = getattr(request.app.state, "started_at", None)
    scheduler = getattr(request.app.state, "scheduler", None)
    telegram_app = getattr(request.app.state, "telegram_app", None)

    uptime_seconds = None
    if started_at:
        uptime_seconds = (datetime.now() - started_at).total_seconds()

    scheduler_jobs = []
    if scheduler:
        for job in scheduler.get_jobs():
            scheduler_jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                }
            )

    return {
        "status": "healthy",
        "started_at": str(started_at) if started_at else None,
        "uptime_seconds": uptime_seconds,
        "scheduler": {
            "running": scheduler is not None and scheduler.running,
            "jobs": scheduler_jobs,
        }
        if scheduler
        else {"running": False, "jobs": []},
        "telegram": {
            "connected": telegram_app is not None,
        },
    }
