-- =====================================================================
-- CI 전용 최소 스키마 (성능 스모크용)
-- 프로덕션 마이그레이션이 ALTER/dedup만 담고 있어 CREATE TABLE이 없으므로,
-- /api/board 쿼리가 동작하는 데 필요한 테이블만 CI에서 생성한다.
-- main.py 의 board 쿼리(contents LEFT JOIN job_postings, GROUP BY)에 맞춘 컬럼.
-- ⚠️ 프로덕션 스키마의 권위 정의가 아니라 CI 픽스처임.
-- =====================================================================

CREATE TABLE IF NOT EXISTS contents (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  source_name VARCHAR(64),
  title       VARCHAR(512),
  raw_content MEDIUMTEXT,
  url         VARCHAR(768),
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_contents_url (url)
);

CREATE TABLE IF NOT EXISTS job_postings (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  content_id     INT,
  employment     VARCHAR(64),
  work_type      VARCHAR(128),
  duty           VARCHAR(255),
  deadline       DATE NULL,
  is_always_open TINYINT(1) DEFAULT 0,
  UNIQUE KEY uk_job_postings_content_id (content_id)
);

CREATE TABLE IF NOT EXISTS keyword (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  keyword_name VARCHAR(128),
  UNIQUE KEY uk_keyword_name (keyword_name)
);
