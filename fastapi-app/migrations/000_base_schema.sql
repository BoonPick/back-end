-- =====================================================================
-- Migration 000: 베이스 스키마 (로컬 부트스트랩용)
--
-- ⚠️ 이 파일은 코드(main.py / crawling_*.py / notifier.py)의 SQL 쿼리에서
--    역으로 재구성한 베이스 스키마입니다. repo 에 원본 스키마 파일이 없어
--    로컬에서 빈 MySQL 을 띄울 때 테이블을 부트스트랩하기 위해 추가했습니다.
--
-- 적용 순서:
--   000_base_schema.sql  (이 파일)  → 테이블 생성 (UNIQUE 제약 없는 초기 상태)
--   001_dedup_and_unique.sql        → contents.url / job_postings.content_id UNIQUE 추가
--   002_notification_settings.sql   → notification_settings 테이블 생성
--   003_notification_search_query.sql → notification_settings.search_query 컬럼 추가
--
-- 001 이 UNIQUE 를 ADD 하므로 이 파일에서는 의도적으로 UNIQUE 를 넣지 않습니다.
-- =====================================================================

-- ── users ────────────────────────────────────────────────────────────
-- 가입/로그인. login_id 와 email 로 조회 (main.py).
CREATE TABLE IF NOT EXISTS users (
    id         BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    login_id   VARCHAR(255) NOT NULL,
    user_name  VARCHAR(255)     NULL,
    password   VARCHAR(255)     NULL,
    email      VARCHAR(255) NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_users_login_id (login_id),
    UNIQUE KEY uk_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── email_verifications ──────────────────────────────────────────────
-- 가입 이메일 인증 코드. (main.py: code/expires_at/verified/attempts/created_at)
CREATE TABLE IF NOT EXISTS email_verifications (
    id         BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(255) NOT NULL,
    code       VARCHAR(16)  NOT NULL,
    expires_at DATETIME     NOT NULL,
    verified   TINYINT(1)   NOT NULL DEFAULT 0,
    attempts   INT          NOT NULL DEFAULT 0,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_email_verifications_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── contents ─────────────────────────────────────────────────────────
-- 크롤링된 공지/장학/채용 콘텐츠. url 기준 upsert (ON DUPLICATE KEY).
-- UNIQUE(url) 는 001 에서 추가되므로 여기선 일반 컬럼으로만 둔다.
CREATE TABLE IF NOT EXISTS contents (
    id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(512)     NULL,
    source_name VARCHAR(255)     NULL,
    category    VARCHAR(64)      NULL,
    url         VARCHAR(512) NOT NULL,
    raw_content LONGTEXT         NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── job_postings ─────────────────────────────────────────────────────
-- 채용 콘텐츠의 부가 정보. content_id 기준 upsert (ON DUPLICATE KEY).
-- UNIQUE(content_id) 는 001 에서 추가.
CREATE TABLE IF NOT EXISTS job_postings (
    id             BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
    content_id     BIGINT      NOT NULL,
    employment     VARCHAR(64)     NULL,
    work_type      VARCHAR(255)    NULL,
    duty           VARCHAR(255)    NULL,
    deadline       DATETIME        NULL,
    is_always_open TINYINT(1)  NOT NULL DEFAULT 0,
    KEY idx_job_postings_content_id (content_id),
    CONSTRAINT fk_job_postings_content
        FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── keyword ──────────────────────────────────────────────────────────
-- 관리자용 키워드. 중복은 앱 레벨에서 검사(main.py)하므로 UNIQUE 미설정.
CREATE TABLE IF NOT EXISTS keyword (
    id           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    keyword_name VARCHAR(255) NOT NULL,
    KEY idx_keyword_name (keyword_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
