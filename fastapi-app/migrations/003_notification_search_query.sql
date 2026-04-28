-- =====================================================================
-- Migration 003: notification_settings에 search_query(제목 검색) 컬럼 추가
-- =====================================================================

ALTER TABLE notification_settings
    ADD COLUMN search_query VARCHAR(255) NULL AFTER work_types;

-- 검증:
-- DESCRIBE notification_settings;
