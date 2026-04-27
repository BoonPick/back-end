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
from crawling_job import crawl_jobs

KST = ZoneInfo("Asia/Seoul")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def noti_crawl():
    logger.info("공지 크롤링 시작")
    try:
        saved = crawl_notices(page_count=2)
        logger.info(f"공지 크롤링 완료 — {saved}건 저장됨")
    except Exception as e:
        logger.error(f"공지 크롤링 오류: {e}")


def job_posting_crawl():
    logger.info("채용 크롤링 시작")
    try:
        saved = crawl_jobs(page_count=3)
        logger.info(f"채용 크롤링 완료 — {saved}건 저장됨")
    except Exception as e:
        logger.error(f"채용 크롤링 오류: {e}")


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(
        noti_crawl,
        trigger="cron",
        hour=2,
        minute=15,
        timezone=KST,
        id="daily_noti_crawl",
    )
    scheduler.add_job(
        job_posting_crawl,
        trigger="cron",
        hour=2,
        minute=30,
        timezone=KST,
        id="daily_job_crawl",
    )

    logger.info("스케줄러 시작 — 매일 오전 2시 공지/채용 크롤링")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
