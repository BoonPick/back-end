"""
독립 실행 스케줄러 — FastAPI 앱과 별도 프로세스로 실행합니다.

실행 방법:
    python scheduler.py

서버(Linux) cron 등록 예시:
    @reboot cd /app && python scheduler.py >> /var/log/scheduler.log 2>&1 &
"""

import logging
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler

from crawling_noti import crawl_notices

KST = ZoneInfo("Asia/Seoul")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def job_crawl():
    logger.info("크롤링 시작")
    try:
        saved = crawl_notices(page_count=2)
        logger.info(f"크롤링 완료 — {saved}건 저장됨")
    except Exception as e:
        logger.error(f"크롤링 오류: {e}")


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(
        job_crawl,
        trigger="cron",
        hour=2,
        minute=10,
        timezone=KST,
        id="daily_crawl",
    )

    logger.info("스케줄러 시작 — 매일 오전 2시 크롤링")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
