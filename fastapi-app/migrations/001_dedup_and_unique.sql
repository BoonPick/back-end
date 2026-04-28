-- =====================================================================
-- Migration 001: 중복 row 정리 + UNIQUE 제약 추가
--
-- 적용 순서:
--   1) 기존 중복 row 정리 (가장 작은 id만 남김)
--   2) UNIQUE 제약 추가
--
-- 안전장치:
--   - 트랜잭션으로 묶어 실패 시 롤백
--   - DELETE 전 SELECT으로 영향 범위 확인 가능
--   - 백업 권장: mysqldump --single-transaction boonpick > backup.sql
-- =====================================================================

START TRANSACTION;

-- ── 1. job_postings 중복 정리 ────────────────────────────────────────
-- 같은 content_id에 row가 여러 개면 가장 작은 id만 남기고 삭제.

DELETE jp1 FROM job_postings jp1
INNER JOIN job_postings jp2
  ON jp1.content_id = jp2.content_id
 AND jp1.id > jp2.id;

-- ── 2. contents 중복 정리 ───────────────────────────────────────────
-- 같은 url에 row가 여러 개면 가장 작은 id만 남기고 삭제.
-- 자식(job_postings)을 먼저 정리한 뒤 contents 정리.
-- 외래키 ON DELETE CASCADE가 없을 가능성 대비, 자식 row를
-- 살아남는 contents id로 이관.

UPDATE job_postings jp
INNER JOIN contents c_dup ON jp.content_id = c_dup.id
INNER JOIN (
    SELECT url, MIN(id) AS keep_id
    FROM contents
    GROUP BY url
) c_keep ON c_dup.url = c_keep.url
SET jp.content_id = c_keep.keep_id
WHERE c_dup.id <> c_keep.keep_id;

DELETE c1 FROM contents c1
INNER JOIN contents c2
  ON c1.url = c2.url
 AND c1.id > c2.id;

-- 위 UPDATE로 동일 keep_id에 다시 중복이 생겼을 수 있으므로 재정리.
DELETE jp1 FROM job_postings jp1
INNER JOIN job_postings jp2
  ON jp1.content_id = jp2.content_id
 AND jp1.id > jp2.id;

-- ── 3. UNIQUE 제약 추가 ─────────────────────────────────────────────

ALTER TABLE contents
    ADD UNIQUE KEY uk_contents_url (url);

ALTER TABLE job_postings
    ADD UNIQUE KEY uk_job_postings_content_id (content_id);

COMMIT;

-- ── 검증 쿼리 ────────────────────────────────────────────────────────
-- 적용 후 다음 쿼리 결과가 모두 0건이어야 정상.
--
-- SELECT url, COUNT(*) FROM contents GROUP BY url HAVING COUNT(*) > 1;
-- SELECT content_id, COUNT(*) FROM job_postings GROUP BY content_id HAVING COUNT(*) > 1;
