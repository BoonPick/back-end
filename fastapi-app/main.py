from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from typing import List, Optional
import os
from datetime import datetime

import mysql.connector

from llm import get_llm_recommendation
import crawling_noti
import crawling_job


# ── DB ───────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "boonpick"),
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# ── App ──────────────────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://163.239.77.78:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────

class KeywordCreateRequest(BaseModel):
    keyword_name: str


class KeywordUpdateRequest(BaseModel):
    keyword_name: str


class KeywordResponse(BaseModel):
    id: int
    keyword_name: str


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    keywords: List[str] = []


class BoardItem(BaseModel):
    id: str
    category: str
    title: str
    summary: str
    body: str
    source: str
    sourceUrl: str
    date: str
    keywords: List[str] = []
    employment: Optional[str] = None
    workType: Optional[str] = None
    duty: Optional[str] = None
    deadline: Optional[str] = None
    isAlwaysOpen: Optional[bool] = None


class Recommendation(BaseModel):
    itemId: str
    matchScore: int
    matchReason: str
    preparationTips: List[str]


class DedupGroupSample(BaseModel):
    title: str
    work_type: Optional[str] = None
    count: int
    ids: str  # GROUP_CONCAT 결과 ("3,7,15")


class DedupJobsResponse(BaseModel):
    dry_run: bool
    groups: int            # 중복 그룹 수
    affected_rows: int     # 삭제 대상(또는 삭제됨) row 수
    samples: List[DedupGroupSample]


# ── Auth (users: id, login_id, user_name, password, email) ──────

def _user_to_response(user_row: dict) -> UserResponse:
    return UserResponse(
        id=str(user_row["id"]),
        email=user_row.get("email") or user_row.get("login_id") or "",
        name=user_row.get("user_name") or "",
    )


@app.post("/api/auth/signup", response_model=UserResponse)
def signup(req: SignupRequest):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE login_id = %s", (req.email,))
        if cursor.fetchone():
            raise HTTPException(400, "이미 가입된 이메일입니다.")
        cursor.execute(
            "INSERT INTO users (login_id, user_name, password, email) VALUES (%s, %s, %s, %s)",
            (req.email, req.name, req.password, req.email),
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = %s", (cursor.lastrowid,))
        user = cursor.fetchone()
        cursor.close()
        return _user_to_response(user)
    finally:
        conn.close()


@app.post("/api/auth/login", response_model=UserResponse)
def login(req: LoginRequest):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE login_id = %s OR email = %s",
            (req.email, req.email),
        )
        user = cursor.fetchone()
        if not user:
            # PoC: 없는 계정이면 자동 생성
            cursor.execute(
                "INSERT INTO users (login_id, user_name, password, email) VALUES (%s, %s, %s, %s)",
                (req.email, req.email.split("@")[0], req.password, req.email),
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE id = %s", (cursor.lastrowid,))
            user = cursor.fetchone()
        cursor.close()
        return _user_to_response(user)
    finally:
        conn.close()


# ── Keywords (keyword: id, keyword_name) ─────────────────────────

@app.get("/api/keywords", response_model=List[str])
def get_keywords():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT keyword_name FROM keyword ORDER BY keyword_name")
        keywords = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return keywords
    finally:
        conn.close()


# ── Admin Keywords CRUD ──────────────────────────────────────────

@app.get("/api/admin/keywords", response_model=List[KeywordResponse])
def admin_get_keywords():
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, keyword_name FROM keyword ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


@app.post("/api/admin/keywords", response_model=KeywordResponse, status_code=201)
def admin_create_keyword(req: KeywordCreateRequest):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM keyword WHERE keyword_name = %s", (req.keyword_name,)
        )
        if cursor.fetchone():
            raise HTTPException(400, "이미 존재하는 키워드입니다.")
        cursor.execute(
            "INSERT INTO keyword (keyword_name) VALUES (%s)", (req.keyword_name,)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        return KeywordResponse(id=new_id, keyword_name=req.keyword_name)
    finally:
        conn.close()


@app.put("/api/admin/keywords/{keyword_id}", response_model=KeywordResponse)
def admin_update_keyword(keyword_id: int, req: KeywordUpdateRequest):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM keyword WHERE id = %s", (keyword_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "키워드를 찾을 수 없습니다.")
        cursor.execute(
            "SELECT id FROM keyword WHERE keyword_name = %s AND id != %s",
            (req.keyword_name, keyword_id),
        )
        if cursor.fetchone():
            raise HTTPException(400, "이미 존재하는 키워드입니다.")
        cursor.execute(
            "UPDATE keyword SET keyword_name = %s WHERE id = %s",
            (req.keyword_name, keyword_id),
        )
        conn.commit()
        cursor.close()
        return KeywordResponse(id=keyword_id, keyword_name=req.keyword_name)
    finally:
        conn.close()


@app.delete("/api/admin/keywords/{keyword_id}", status_code=204)
def admin_delete_keyword(keyword_id: int):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM keyword WHERE id = %s", (keyword_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "키워드를 찾을 수 없습니다.")
        cursor.execute("DELETE FROM keyword WHERE id = %s", (keyword_id,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# ── Contents (Board) ─────────────────────────────────────────────

CATEGORY_MAP = {
    "sogang_notice": "announcement",
    "sogang_scholarship": "scholarship",
    "sogang_job": "job",
}


def _row_to_board_item(row: dict) -> BoardItem:
    source_name = row.get("source_name") or ""
    category = CATEGORY_MAP.get(source_name, "announcement")
    raw = row.get("raw_content") or ""
    summary = raw[:200].replace("\n", " ").strip()
    if len(raw) > 200:
        summary += "..."
    created = row.get("created_at")
    date_str = created.strftime("%Y-%m-%d") if created else ""

    deadline = row.get("deadline")
    deadline_str = deadline.strftime("%Y-%m-%d") if deadline else None

    return BoardItem(
        id=str(row["id"]),
        category=category,
        title=row.get("title") or "",
        summary=summary,
        body=raw,
        source=source_name,
        sourceUrl=row.get("url") or "",
        date=date_str,
        employment=row.get("employment"),
        workType=row.get("work_type"),
        duty=row.get("duty"),
        deadline=deadline_str,
        isAlwaysOpen=bool(row.get("is_always_open")) if row.get("is_always_open") is not None else None,
    )


@app.get("/api/board", response_model=List[BoardItem])
def get_board_items(
    category: Optional[str] = None,
    keywords: Optional[str] = None,
    search: Optional[str] = None,
    duty: Optional[str] = None,
    work_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)

        conditions = []
        params = []

        # category filter
        if category:
            source_names = [k for k, v in CATEGORY_MAP.items() if v == category]
            if source_names:
                placeholders = ",".join(["%s"] * len(source_names))
                conditions.append(f"c.source_name IN ({placeholders})")
                params.extend(source_names)

        # keyword recommendation filter (title OR raw_content LIKE)
        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
        if keyword_list:
            kw_clauses = []
            for kw in keyword_list:
                kw_clauses.append("(c.title LIKE %s OR c.raw_content LIKE %s)")
                params.extend([f"%{kw}%", f"%{kw}%"])
            conditions.append(f"({' OR '.join(kw_clauses)})")

        # title search
        if search:
            conditions.append("c.title LIKE %s")
            params.append(f"%{search}%")

        # duty filter (job_postings only)
        if duty:
            conditions.append("jp.duty = %s")
            params.append(duty)

        # work_type filter (job_postings only)
        if work_type:
            conditions.append("jp.work_type = %s")
            params.append(work_type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        offset = (page - 1) * size

        # GROUP BY c.id + MAX 집계: job_postings에 같은 content_id로
        # 중복 row가 있더라도 board 결과가 중복 노출되지 않도록 방어.
        query = (
            f"SELECT c.*, "
            f"MAX(jp.employment)     AS employment, "
            f"MAX(jp.work_type)      AS work_type, "
            f"MAX(jp.duty)           AS duty, "
            f"MAX(jp.deadline)       AS deadline, "
            f"MAX(jp.is_always_open) AS is_always_open "
            f"FROM contents c "
            f"LEFT JOIN job_postings jp ON jp.content_id = c.id "
            f"{where} "
            f"GROUP BY c.id "
            f"ORDER BY c.created_at DESC LIMIT %s OFFSET %s"
        )
        params.extend([size, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()

        return [_row_to_board_item(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/board/{item_id}", response_model=BoardItem)
def get_board_item(item_id: int):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT c.*, "
            "MAX(jp.employment)     AS employment, "
            "MAX(jp.work_type)      AS work_type, "
            "MAX(jp.duty)           AS duty, "
            "MAX(jp.deadline)       AS deadline, "
            "MAX(jp.is_always_open) AS is_always_open "
            "FROM contents c LEFT JOIN job_postings jp ON jp.content_id = c.id "
            "WHERE c.id = %s "
            "GROUP BY c.id",
            (item_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise HTTPException(404, "게시글을 찾을 수 없습니다.")
        return _row_to_board_item(row)
    finally:
        conn.close()


# ── Recommendation (LLM) ────────────────────────────────────────

@app.get("/api/recommendations/{item_id}", response_model=Recommendation)
def get_recommendation(item_id: int, keywords: str = Query("")):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM contents WHERE id = %s", (item_id,))
        content = cursor.fetchone()
        cursor.close()
        if not content:
            raise HTTPException(404, "게시글을 찾을 수 없습니다.")

        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not keyword_list:
            return Recommendation(
                itemId=str(item_id),
                matchScore=0,
                matchReason="키워드를 설정하면 맞춤 추천을 받을 수 있습니다.",
                preparationTips=["관심 키워드를 먼저 설정해주세요."],
            )

        result = get_llm_recommendation(
            keywords=keyword_list,
            title=content.get("title", ""),
            category=content.get("category", ""),
            raw_content=content.get("raw_content", ""),
        )

        return Recommendation(itemId=str(item_id), **result)
    finally:
        conn.close()


# ── Admin / Crawl ────────────────────────────────────────────────

@app.post("/api/admin/crawl")
def trigger_crawl(page_count: int = Query(5, ge=1, le=20)):
    saved = crawling_noti.crawl_notices(page_count=page_count)
    return {"saved": saved, "page_count": page_count}


@app.post("/api/admin/crawl/jobs")
def trigger_job_crawl(page_count: int = Query(3, ge=1, le=20)):
    saved = crawling_job.crawl_jobs(page_count=page_count)
    return {"saved": saved, "page_count": page_count}


# ── Admin / Dedup ────────────────────────────────────────────────

@app.post("/api/admin/dedup/jobs", response_model=DedupJobsResponse)
def dedup_jobs_by_title_worktype(
    dry_run: bool = Query(True, description="True면 영향 범위만 반환, False면 실제 삭제"),
):
    """
    같은 (title, work_type) 조합으로 등록된 채용공고 중 가장 작은 id만 남기고 나머지 삭제.

    - 대상: `source_name = 'sogang_job'`
    - 기본은 `dry_run=True` — 영향 범위와 샘플(최대 20개)만 반환
    - 실제 삭제: `?dry_run=false`
    - 자식(`job_postings`) → 부모(`contents`) 순으로 삭제하며 단일 트랜잭션
    - `work_type IS NULL`은 SQL NULL 비교 규칙상 별도 그룹으로 취급
    """
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)

        # 1) 영향 범위 파악
        cursor.execute(
            """
            SELECT c.title,
                   jp.work_type,
                   COUNT(*) AS cnt,
                   GROUP_CONCAT(c.id ORDER BY c.id) AS ids
            FROM contents c
            INNER JOIN job_postings jp ON jp.content_id = c.id
            WHERE c.source_name = 'sogang_job'
            GROUP BY c.title, jp.work_type
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            """
        )
        groups = cursor.fetchall()
        affected = sum(int(g["cnt"]) - 1 for g in groups)
        samples = [
            DedupGroupSample(
                title=g["title"],
                work_type=g["work_type"],
                count=int(g["cnt"]),
                ids=g["ids"],
            )
            for g in groups[:20]
        ]

        if dry_run or affected == 0:
            cursor.close()
            return DedupJobsResponse(
                dry_run=True,
                groups=len(groups),
                affected_rows=affected,
                samples=samples,
            )

        # 2) 실제 삭제 (트랜잭션)
        try:
            cursor.execute("DROP TEMPORARY TABLE IF EXISTS _dedup_targets")
            cursor.execute(
                """
                CREATE TEMPORARY TABLE _dedup_targets AS
                SELECT c.id
                FROM contents c
                INNER JOIN job_postings jp ON jp.content_id = c.id
                INNER JOIN (
                    SELECT c2.title, jp2.work_type, MIN(c2.id) AS keep_id
                    FROM contents c2
                    INNER JOIN job_postings jp2 ON jp2.content_id = c2.id
                    WHERE c2.source_name = 'sogang_job'
                    GROUP BY c2.title, jp2.work_type
                    HAVING COUNT(*) > 1
                ) k
                  ON (k.title = c.title)
                 AND (k.work_type <=> jp.work_type)
                WHERE c.source_name = 'sogang_job'
                  AND c.id <> k.keep_id
                """
            )
            cursor.execute(
                "DELETE FROM job_postings WHERE content_id IN (SELECT id FROM _dedup_targets)"
            )
            cursor.execute(
                "DELETE FROM contents WHERE id IN (SELECT id FROM _dedup_targets)"
            )
            deleted = cursor.rowcount
            cursor.execute("DROP TEMPORARY TABLE IF EXISTS _dedup_targets")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        cursor.close()
        return DedupJobsResponse(
            dry_run=False,
            groups=len(groups),
            affected_rows=deleted,
            samples=samples,
        )
    finally:
        conn.close()


# ── Legacy / Static ──────────────────────────────────────────────

@app.get("/")
def read_index():
    return FileResponse("templates/index.html")
