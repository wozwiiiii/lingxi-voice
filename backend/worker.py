"""Celery worker app definition."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "lingxi_voice",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.clone_service", "app.tasks.courseware_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 定时任务调度（Celery Beat 三合一）：
    # - cleanup_orphan_courseware：每天凌晨删 7 天前的弃置课件
    # - cleanup_orphan_audio：每天凌晨删 30 天前无引用的音频
    # - converge_stuck_projects：每 10 分钟收敛卡死在 synthesizing 的项目
    beat_schedule={
        "cleanup-orphan-courseware": {
            "task": "app.tasks.courseware_tasks.cleanup_orphan_courseware",
            "schedule": crontab(hour=3, minute=0),
        },
        "cleanup-orphan-audio": {
            "task": "app.tasks.courseware_tasks.cleanup_orphan_audio",
            "schedule": crontab(hour=3, minute=30),
        },
        "converge-stuck-projects": {
            "task": "app.tasks.courseware_tasks.converge_stuck_projects",
            "schedule": crontab(minute="*/10"),
        },
    },
)
