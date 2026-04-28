"""
알림 발송 모듈 — 크롤 후 호출되어 사용자별 매칭 게시물을 메일로 보낸다.

호출 흐름:
    scheduler.py: noti_crawl() / job_posting_crawl() 종료 직후
    → notify_new_items_for_all_users()
        - notification_settings의 모든 사용자 순회
        - last_notified_at 이후 contents 중 카테고리/필터 매칭
        - 키워드가 있으면 매칭 점수 ≥ 10인 항목만
        - 한 사용자에게 한 통의 메일로 묶어 발송
        - last_notified_at 업데이트
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

import mysql.connector

import mailer

logger = logging.getLogger(__name__)

# main.py와 동일한 매핑 (의존성 분리 위해 중복 정의)
SOURCE_TO_CATEGORY = {
    "sogang_notice": "announcement",
    "sogang_scholarship": "scholarship",
    "sogang_job": "job",
}
CATEGORY_LABELS = {
    "announcement": "학사공지",
    "scholarship": "장학금공지",
    "job": "채용공고",
}
SCORE_THRESHOLD = 10  # 매칭 점수 임계값 (%)
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "")


def _db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "boonpick"),
    )


def _split(s: str | None) -> list[str]:
    if not s:
        return []
    return [t.strip() for t in s.split(",") if t.strip()]


def _match_score(item_title: str, item_content: str, keywords: list[str]) -> int:
    """단순 키워드 포함 비율 기반 매칭 점수 (0~100)."""
    if not keywords:
        return 100  # 키워드 없으면 통과 (필터만 적용)
    haystack = f"{item_title or ''} {item_content or ''}".lower()
    hits = sum(1 for k in keywords if k.lower() in haystack)
    return int(round(hits / len(keywords) * 100))


def _summary(raw: str | None, n: int = 200) -> str:
    raw = (raw or "").replace("\n", " ").strip()
    return raw[:n] + ("..." if len(raw) > n else "")


def _fetch_new_items(cursor, last_notified_at, categories: list[str]):
    """last_notified_at 이후 created_at의 contents를 카테고리에 맞게 조회."""
    sources = [
        s for s, c in SOURCE_TO_CATEGORY.items() if c in categories
    ]
    if not sources:
        return []
    placeholders = ",".join(["%s"] * len(sources))
    cursor.execute(
        f"""
        SELECT c.id, c.title, c.source_name, c.url, c.raw_content, c.created_at,
               jp.duty, jp.work_type
        FROM contents c
        LEFT JOIN job_postings jp ON jp.content_id = c.id
        WHERE c.source_name IN ({placeholders})
          AND c.created_at > %s
        GROUP BY c.id
        ORDER BY c.created_at DESC
        LIMIT 200
        """,
        (*sources, last_notified_at),
    )
    return cursor.fetchall()


def _job_passes_filters(
    duty: str | None,
    work_type: str | None,
    duty_filters: list[str],
    wt_filters: list[str],
) -> bool:
    def token_match(value: str | None, filters: list[str]) -> bool:
        if not filters:
            return True
        if not value:
            return False
        tokens = {t.strip() for t in value.split(",") if t.strip()}
        return any(f in tokens for f in filters)

    return token_match(duty, duty_filters) and token_match(work_type, wt_filters)


def _build_notification_payload(
    rows: Iterable[dict],
    duty_filters: list[str],
    wt_filters: list[str],
    keywords: list[str],
) -> list[dict]:
    payload = []
    for r in rows:
        category = SOURCE_TO_CATEGORY.get(r["source_name"], "")
        if category == "job":
            if not _job_passes_filters(
                r.get("duty"), r.get("work_type"), duty_filters, wt_filters
            ):
                continue

        score = _match_score(r["title"], r.get("raw_content"), keywords)
        if keywords and score < SCORE_THRESHOLD:
            continue

        link = (
            f"{SITE_BASE_URL.rstrip('/')}/board/{r['id']}"
            if SITE_BASE_URL
            else (r.get("url") or "")
        )
        payload.append(
            {
                "title": r["title"],
                "category_label": CATEGORY_LABELS.get(category, category),
                "source": r["source_name"],
                "url": link,
                "summary": _summary(r.get("raw_content")),
                "score": score if keywords else None,
            }
        )
    return payload


def notify_new_items_for_all_users() -> int:
    """
    모든 알림 설정 사용자에게 매칭 콘텐츠를 메일로 발송.
    반환값: 발송한 메일 수 (= 매칭이 1건 이상인 사용자 수).
    """
    conn = _db()
    sent_count = 0
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT ns.user_id, ns.categories, ns.duties, ns.work_types,
                   ns.keywords, ns.last_notified_at,
                   u.email
            FROM notification_settings ns
            INNER JOIN users u ON u.id = ns.user_id
            WHERE u.email IS NOT NULL AND u.email <> ''
            """
        )
        users = cursor.fetchall()

        for u in users:
            categories = _split(u["categories"])
            duties = _split(u["duties"])
            work_types = _split(u["work_types"])
            keywords = _split(u["keywords"])

            try:
                rows = _fetch_new_items(cursor, u["last_notified_at"], categories)
                items = _build_notification_payload(rows, duties, work_types, keywords)

                if items:
                    mailer.send_notification_email(u["email"], items)
                    sent_count += 1

                # 매칭 0건이어도 last_notified_at은 갱신해 다음 회차에 같은 항목 재평가 안 하게.
                cursor.execute(
                    "UPDATE notification_settings SET last_notified_at = NOW() "
                    "WHERE user_id = %s",
                    (u["user_id"],),
                )
                conn.commit()
            except Exception as e:
                logger.exception(
                    "notification failed for user_id=%s: %s", u["user_id"], e
                )
                # 한 사용자 실패가 전체 중단으로 이어지지 않도록 계속.

        cursor.close()
    finally:
        conn.close()

    logger.info("notification batch complete — %d emails sent", sent_count)
    return sent_count
