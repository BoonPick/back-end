-- =====================================================================
-- CI 전용 시드 데이터 (성능 스모크용)
-- /api/board 가 빈 결과가 아니라 실제 JOIN+GROUP BY 비용을 치르도록
-- 세 카테고리(notice/scholarship/job)에 걸쳐 30개 row 를 넣는다.
-- =====================================================================

-- 한글 데이터 보존을 위해 클라이언트 커넥션 charset 을 명시.
SET NAMES utf8mb4;

-- 공지 12건
INSERT INTO contents (source_name, title, raw_content, url, created_at) VALUES
('sogang_notice', '2026-1학기 수강신청 안내', '수강신청 일정 및 유의사항 본문...', 'https://sogang.test/notice/1', NOW() - INTERVAL 1 DAY),
('sogang_notice', '도서관 운영시간 변경 안내', '시험기간 연장 운영 본문...', 'https://sogang.test/notice/2', NOW() - INTERVAL 2 DAY),
('sogang_notice', '학사일정 정정 공지', '정정된 학사일정 본문...', 'https://sogang.test/notice/3', NOW() - INTERVAL 3 DAY),
('sogang_notice', '교내 셔틀버스 노선 개편', '셔틀 노선 변경 본문...', 'https://sogang.test/notice/4', NOW() - INTERVAL 4 DAY),
('sogang_notice', '졸업요건 변경 안내', '졸업요건 본문...', 'https://sogang.test/notice/5', NOW() - INTERVAL 5 DAY),
('sogang_notice', '계절학기 등록 안내', '계절학기 본문...', 'https://sogang.test/notice/6', NOW() - INTERVAL 6 DAY),
('sogang_notice', '교환학생 모집 설명회', '교환학생 본문...', 'https://sogang.test/notice/7', NOW() - INTERVAL 7 DAY),
('sogang_notice', 'IT 시스템 점검 공지', '점검 본문...', 'https://sogang.test/notice/8', NOW() - INTERVAL 8 DAY),
('sogang_notice', '학생증 재발급 안내', '학생증 본문...', 'https://sogang.test/notice/9', NOW() - INTERVAL 9 DAY),
('sogang_notice', '동아리 등록 기간 안내', '동아리 본문...', 'https://sogang.test/notice/10', NOW() - INTERVAL 10 DAY),
('sogang_notice', '교내 주차 정책 변경', '주차 본문...', 'https://sogang.test/notice/11', NOW() - INTERVAL 11 DAY),
('sogang_notice', '학생식당 메뉴 개편', '식당 본문...', 'https://sogang.test/notice/12', NOW() - INTERVAL 12 DAY);

-- 장학 6건
INSERT INTO contents (source_name, title, raw_content, url, created_at) VALUES
('sogang_scholarship', '2026 국가장학금 신청 안내', '국가장학금 본문...', 'https://sogang.test/sch/1', NOW() - INTERVAL 1 DAY),
('sogang_scholarship', '교내 성적우수 장학', '성적우수 본문...', 'https://sogang.test/sch/2', NOW() - INTERVAL 2 DAY),
('sogang_scholarship', '근로장학 모집', '근로장학 본문...', 'https://sogang.test/sch/3', NOW() - INTERVAL 3 DAY),
('sogang_scholarship', '동문 후원 장학', '동문 본문...', 'https://sogang.test/sch/4', NOW() - INTERVAL 4 DAY),
('sogang_scholarship', '저소득층 생활지원 장학', '생활지원 본문...', 'https://sogang.test/sch/5', NOW() - INTERVAL 5 DAY),
('sogang_scholarship', '해외연수 장학', '해외연수 본문...', 'https://sogang.test/sch/6', NOW() - INTERVAL 6 DAY);

-- 채용 12건 (job_postings 연결)
INSERT INTO contents (source_name, title, raw_content, url, created_at) VALUES
('sogang_job', '백엔드 개발 인턴 채용', 'Python/FastAPI 백엔드 본문...', 'https://sogang.test/job/1', NOW() - INTERVAL 1 DAY),
('sogang_job', '프론트엔드 개발자 채용', 'React 프론트엔드 본문...', 'https://sogang.test/job/2', NOW() - INTERVAL 2 DAY),
('sogang_job', '데이터 엔지니어 채용', '데이터 파이프라인 본문...', 'https://sogang.test/job/3', NOW() - INTERVAL 3 DAY),
('sogang_job', 'AI 리서치 인턴', 'LLM 리서치 본문...', 'https://sogang.test/job/4', NOW() - INTERVAL 4 DAY),
('sogang_job', 'DevOps 엔지니어 채용', 'CI/CD 본문...', 'https://sogang.test/job/5', NOW() - INTERVAL 5 DAY),
('sogang_job', 'QA 엔지니어 채용', '테스트 자동화 본문...', 'https://sogang.test/job/6', NOW() - INTERVAL 6 DAY),
('sogang_job', '모바일 앱 개발자', 'iOS/Android 본문...', 'https://sogang.test/job/7', NOW() - INTERVAL 7 DAY),
('sogang_job', '보안 엔지니어 채용', '보안 본문...', 'https://sogang.test/job/8', NOW() - INTERVAL 8 DAY),
('sogang_job', '클라우드 아키텍트', 'AWS 본문...', 'https://sogang.test/job/9', NOW() - INTERVAL 9 DAY),
('sogang_job', 'PM 인턴 채용', '프로덕트 본문...', 'https://sogang.test/job/10', NOW() - INTERVAL 10 DAY),
('sogang_job', 'UX 디자이너 채용', '디자인 본문...', 'https://sogang.test/job/11', NOW() - INTERVAL 11 DAY),
('sogang_job', '머신러닝 엔지니어', 'ML 본문...', 'https://sogang.test/job/12', NOW() - INTERVAL 12 DAY);

-- 채용 글에 job_postings 연결 (source_name='sogang_job' 인 contents 기준)
INSERT INTO job_postings (content_id, employment, work_type, duty, deadline, is_always_open)
SELECT c.id,
       CASE WHEN c.id % 2 = 0 THEN '정규직' ELSE '인턴' END,
       CASE WHEN c.id % 3 = 0 THEN '재택' ELSE '출근' END,
       '개발',
       DATE(NOW() + INTERVAL (c.id % 30) DAY),
       c.id % 5
FROM contents c
WHERE c.source_name = 'sogang_job';

-- 추천 키워드
INSERT INTO keyword (keyword_name) VALUES
('AI'), ('백엔드'), ('프론트엔드'), ('데이터'), ('장학금'), ('인턴');
