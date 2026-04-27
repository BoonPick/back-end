import requests
import os
import mysql.connector
from bs4 import BeautifulSoup
from pdfviewer import find_pdf_urls, download_pdf, extract_pdf_text


BASE_URL = "https://www.sogang.ac.kr"

# 크롤링할 게시판 설정
# bbs_config_fk: API 파라미터, page_url: 공지 상세 페이지 URL 기준 (중복 체크용)
BOARDS = [
    {
        "source_name": "sogang_notice",
        "bbs_config_fk": 2,
        "page_size": 15,
        "page_url": f"{BASE_URL}/ko/notice",
    },
    {
        "source_name": "sogang_scholarship",
        "bbs_config_fk": 141,
        "page_size": 16,
        "page_url": f"{BASE_URL}/ko/notice",
    },
]

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "boonpick"),
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def notice_exists(cursor, notice_url: str) -> bool:
    """URL로 이미 DB에 저장된 공지인지 확인"""
    cursor.execute("SELECT id FROM contents WHERE url = %s", (notice_url,))
    return cursor.fetchone() is not None


def extract_category_from_title(title: str) -> tuple[str, str]:
    """
    제목 앞의 [카테고리] 패턴을 추출해 (category, 순수제목) 반환.
    예: '[장학] 2025년 장학생 모집' → ('장학', '2025년 장학생 모집')
    패턴 없으면 ('', 원본제목) 반환.
    """
    import re
    match = re.match(r"^\[([^\]]+)\]\s*", title)
    if match:
        category = match.group(1).strip()
        clean_title = title[match.end():].strip()
        return category, clean_title
    return "", title


def parse_notice_date(notice: dict):
    """
    API 응답에서 공지 게시 날짜를 파싱. 여러 필드명을 순서대로 시도.
    파싱 성공 시 datetime 반환, 실패 시 None 반환.
    """
    from datetime import datetime as dt
    candidates = ["createDate", "registDate", "regDate", "writeDate", "modifyDate", "updDate"]
    for field in candidates:
        raw = notice.get(field)
        if not raw:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M%S", "%Y%m%d"):
            try:
                return dt.strptime(str(raw)[:19], fmt)
            except ValueError:
                continue
    return None


def save_notice(cursor, title: str, source_name: str, category: str,
                url: str, raw_content: str, posted_at=None):
    """공지를 DB에 저장 (본문 + PDF 텍스트 모두 raw_content에 포함)"""
    if posted_at is not None:
        cursor.execute(
            """
            INSERT INTO contents (title, source_name, category, url, raw_content, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (title, source_name, category, url, raw_content, posted_at),
        )
    else:
        cursor.execute(
            """
            INSERT INTO contents (title, source_name, category, url, raw_content, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (title, source_name, category, url, raw_content),
        )


# ── 메인 크롤링 ──────────────────────────────────────────────────

def crawl_notices(page_count: int = 1):
    """
    모든 게시판을 page_count 페이지만큼 크롤링하여 DB에 저장.
    이미 존재하는 pkId는 건너뜀.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_count = 0

    try:
        for board in BOARDS:
            source_name = board["source_name"]
            bbs_config_fk = board["bbs_config_fk"]
            page_url = board["page_url"]
            page_size = board["page_size"]

            print(f"\n[{source_name}] 크롤링 시작 ({page_count}페이지)")

            for page in range(1, page_count + 1):
                list_url = (
                    f"{BASE_URL}/api/api/v1/mainKo/BbsData/boardList"
                    f"?pageNum={page}&pageSize={page_size}&bbsConfigFk={bbs_config_fk}"
                    "&category&introPkId&title&content&username"
                )
                response = requests.get(list_url)
                data = response.json()

                if not data.get("data") or not data["data"].get("list"):
                    print(f"  [{source_name}] page={page} 응답 없음 또는 빈 목록, 건너뜀")
                    print(f"  응답: {data}")
                    continue

                notices = data["data"]["list"]

                for n in notices:
                    pkId = n["pkId"]
                    raw_title = n["title"]
                    extracted_category, title = extract_category_from_title(raw_title)
                    category = extracted_category or n.get("category", "") or ""

                    notice_url = f"{page_url}?bbsConfigFk={bbs_config_fk}&pkId={pkId}"

                    # 이미 DB에 있으면 건너뜀
                    if notice_exists(cursor, notice_url):
                        print(f"  SKIP (이미 존재): [{pkId}] {title}")
                        continue

                    # 공지 상세 요청
                    detail_url = f"{BASE_URL}/api/api/v1/mainKo/BbsData?pkId={pkId}"
                    detail_resp = requests.get(detail_url)
                    detail_data = detail_resp.json()["data"]

                    html = detail_data.get("content", "")
                    soup = BeautifulSoup(html, "html.parser")
                    body_text = soup.get_text(separator="\n", strip=True)

                    # PDF 탐지 및 텍스트 추출 → 본문과 합침
                    content_parts = [body_text]
                    pdf_urls = find_pdf_urls(html, detail_data)
                    if pdf_urls:
                        print(f"  PDF {len(pdf_urls)}개 발견: [{pkId}] {title}")

                        for idx, pdf_url in enumerate(pdf_urls, 1):
                            pdf_path = f"temp_{pkId}_{idx}.pdf"
                            try:
                                download_pdf(pdf_url, pdf_path)
                                result = extract_pdf_text(pdf_path)

                                for page_info in result["pages"]:
                                    content_parts.append(f"[PDF {idx} - Page {page_info['page']}]\n{page_info['text']}")

                                for table_info in result["tables"]:
                                    rows = "\n".join(str(row) for row in table_info["data"])
                                    content_parts.append(f"[PDF {idx} - Table Page {table_info['page']}]\n{rows}")

                            except Exception as e:
                                print(f"    PDF 오류: {e}")
                                content_parts.append(f"[PDF 오류: {e}]")

                            finally:
                                if os.path.exists(pdf_path):
                                    os.remove(pdf_path)

                    raw_content = "\n\n".join(content_parts)

                    posted_at = parse_notice_date(n) or parse_notice_date(detail_data)
                    save_notice(cursor, title, source_name, category,
                                notice_url, raw_content, posted_at=posted_at)
                    conn.commit()
                    saved_count += 1
                    date_label = posted_at.strftime("%Y-%m-%d") if posted_at else "날짜 미확인(NOW 사용)"
                    print(f"  SAVED: [{pkId}] {title} ({date_label})")

    finally:
        cursor.close()
        conn.close()

    print(f"\n완료! 총 {saved_count}건 저장됨")
    return saved_count


if __name__ == "__main__":
    crawl_notices(page_count=5)
