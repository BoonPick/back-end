from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from typing import List, Optional
import os
from datetime import datetime

import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler

from crawling_noti import crawl_notices


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "163.239.77.78"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "devops"),
    "password": os.getenv("DB_PASSWORD", "Sogangteam2~!"),
    "database": os.getenv("DB_NAME", "boonpick"),
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ── 스케줄러 설정 (매일 오전 6시, 1페이지만) ──────────────────────

scheduler = BackgroundScheduler()
scheduler.add_job(
    lambda: crawl_notices(page_count=1),
    trigger="cron",
    hour=6,
    minute=0,
    id="daily_crawl",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    print("스케줄러 시작 (매일 오전 6시 크롤링)")
    yield
    scheduler.shutdown()
    print("스케줄러 종료")


app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_index():
    return FileResponse("templates/index.html")


# ── 수동 크롤링 트리거 ────────────────────────────────────────────

@app.post("/crawl")
def trigger_crawl(page_count: int = 1):
    """수동으로 크롤링 실행 (기본 1페이지)"""
    try:
        saved = crawl_notices(page_count=page_count)
        return {"status": "ok", "saved_count": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Contents API ─────────────────────────────────────────────────

class Content(BaseModel):
    id: int
    title: str
    source_name: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    raw_content: Optional[str] = None
    refined_content: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@app.get("/contents", response_model=List[Content])
def get_contents():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM contents ORDER BY id DESC")
        rows = cursor.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
