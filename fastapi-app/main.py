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
    keywords: List[str]


class KeywordsRequest(BaseModel):
    keywords: List[str]


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


class Recommendation(BaseModel):
    itemId: str
    matchScore: int
    matchReason: str
    preparationTips: List[str]


# ── Auth ─────────────────────────────────────────────────────────

def _user_to_response(user_row: dict, conn) -> UserResponse:
    cursor = conn.cursor()
    cursor.execute("SELECT keyword FROM user_keywords WHERE user_id = %s", (user_row["id"],))
    keywords = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return UserResponse(
        id=str(user_row["id"]),
        email=user_row["email"],
        name=user_row["name"],
        keywords=keywords,
    )


@app.post("/api/auth/signup", response_model=UserResponse)
def signup(req: SignupRequest):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (req.email,))
        if cursor.fetchone():
            raise HTTPException(400, "이미 가입된 이메일입니다.")
        cursor.execute(
            "INSERT INTO users (email, name, password) VALUES (%s, %s, %s)",
            (req.email, req.name, req.password),
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = %s", (cursor.lastrowid,))
        user = cursor.fetchone()
        cursor.close()
        return _user_to_response(user, conn)
    finally:
        conn.close()


@app.post("/api/auth/login", response_model=UserResponse)
def login(req: LoginRequest):
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (req.email,))
        user = cursor.fetchone()
        cursor.close()
        if not user:
            # PoC: 없는 계정이면 자동 생성
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO users (email, name, password) VALUES (%s, %s, %s)",
                (req.email, req.email.split("@")[0], req.password),
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE id = %s", (cursor.lastrowid,))
            user = cursor.fetchone()
            cursor.close()
        return _user_to_response(user, conn)
    finally:
        conn.close()


# ── Keywords ─────────────────────────────────────────────────────

@app.get("/api/users/{user_id}/keywords", response_model=List[str])
def get_keywords(user_id: int):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT keyword FROM user_keywords WHERE user_id = %s", (user_id,))
        keywords = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return keywords
    finally:
        conn.close()


@app.put("/api/users/{user_id}/keywords", response_model=List[str])
def update_keywords(user_id: int, req: KeywordsRequest):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_keywords WHERE user_id = %s", (user_id,))
        for kw in req.keywords:
            cursor.execute(
                "INSERT INTO user_keywords (user_id, keyword) VALUES (%s, %s)",
                (user_id, kw),
            )
        conn.commit()
        cursor.close()
        return req.keywords
    finally:
        conn.close()


# ── Contents (Board) ─────────────────────────────────────────────

CATEGORY_MAP = {
    "sogang_notice": "announcement",
    "sogang_scholarship": "scholarship",
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

    return BoardItem(
        id=str(row["id"]),
        category=category,
        title=row.get("title") or "",
        summary=summary,
        body=raw,
        source=source_name,
        sourceUrl=row.get("url") or "",
        date=date_str,
    )


@app.get("/api/board", response_model=List[BoardItem])
def get_board_items(
    category: Optional[str] = None,
    keywords: Optional[str] = None,
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
                conditions.append(f"source_name IN ({placeholders})")
                params.extend(source_names)

        # keyword search
        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
        if keyword_list:
            kw_clauses = []
            for kw in keyword_list:
                kw_clauses.append("(title LIKE %s OR raw_content LIKE %s)")
                params.extend([f"%{kw}%", f"%{kw}%"])
            conditions.append(f"({' OR '.join(kw_clauses)})")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        offset = (page - 1) * size

        query = f"SELECT * FROM contents {where} ORDER BY created_at DESC LIMIT %s OFFSET %s"
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
        cursor.execute("SELECT * FROM contents WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise HTTPException(404, "게시글을 찾을 수 없습니다.")
        return _row_to_board_item(row)
    finally:
        conn.close()


# ── Recommendation (LLM) ────────────────────────────────────────

@app.get("/api/recommendations/{item_id}", response_model=Recommendation)
def get_recommendation(item_id: int, user_id: int = Query(...)):
    conn = get_db()
    try:
        # fetch content
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM contents WHERE id = %s", (item_id,))
        content = cursor.fetchone()
        if not content:
            raise HTTPException(404, "게시글을 찾을 수 없습니다.")

        # fetch user keywords
        cursor.execute("SELECT keyword FROM user_keywords WHERE user_id = %s", (user_id,))
        keywords = [row["keyword"] for row in cursor.fetchall()]
        cursor.close()

        if not keywords:
            return Recommendation(
                itemId=str(item_id),
                matchScore=0,
                matchReason="키워드를 설정하면 맞춤 추천을 받을 수 있습니다.",
                preparationTips=["관심 키워드를 먼저 설정해주세요."],
            )

        result = get_llm_recommendation(
            keywords=keywords,
            title=content.get("title", ""),
            category=content.get("category", ""),
            raw_content=content.get("raw_content", ""),
        )

        return Recommendation(itemId=str(item_id), **result)
    finally:
        conn.close()


# ── Legacy / Static ──────────────────────────────────────────────

@app.get("/")
def read_index():
    return FileResponse("templates/index.html")
