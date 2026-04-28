-- =====================================================================
-- Migration 002: 사용자별 이메일 알림 설정 테이블
--
-- 새 공지/장학/채용공고가 등록되면 사용자가 선택한 카테고리·필터에 맞는
-- 콘텐츠를 이메일로 발송하기 위한 설정 저장소.
-- =====================================================================

CREATE TABLE IF NOT EXISTS notification_settings (
    user_id          BIGINT       NOT NULL PRIMARY KEY,
    -- 콤마 구분: 'announcement', 'scholarship', 'job' 중 1개 이상
    categories       VARCHAR(255) NOT NULL,
    -- 콤마 구분, 채용 카테고리에만 적용. 빈 값이면 미적용(전체 매칭).
    duties           TEXT             NULL,
    work_types       VARCHAR(255)     NULL,
    -- 콤마 구분, 옵션. 매칭 점수 산출 시 사용.
    keywords         TEXT             NULL,
    -- 마지막 알림 발송 시점. 이 이후 created_at의 새 콘텐츠만 다음 알림 대상.
    last_notified_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 검증:
-- DESCRIBE notification_settings;
-- SHOW CREATE TABLE notification_settings;
