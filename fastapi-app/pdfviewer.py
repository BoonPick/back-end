import requests
import pdfplumber
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.sogang.ac.kr/",
}

BASE_URL = "https://www.sogang.ac.kr"
DOWNLOAD_BASE = "https://scc.sogang.ac.kr/Download3"


# ── Viewer URL → Download URL 변환 ───────────────────────────────

def to_download_url(url: str) -> str:
    """
    scc.sogang.ac.kr viewer URL에서 pathStr·fileName을 추출해
    Download3 직접 다운로드 URL로 변환.
    pathStr이 없으면 원본 URL을 그대로 반환.
    """
    PATH_STR_KEY = "pathStr%3D"
    FILENAME_KEY = "%26fileName%3D"
    GUBUN_KEY    = "%26gubun"

    pathStr_index  = url.find(PATH_STR_KEY)
    if pathStr_index == -1:
        return url  # pathStr 없으면 변환 불가

    filename_index = url.find(FILENAME_KEY)
    gubun_index    = url.find(GUBUN_KEY)

    # pathStr 값: PATH_STR_KEY 이후 ~ FILENAME_KEY 이전
    path_str_value = url[pathStr_index + len(PATH_STR_KEY) : filename_index]

    # fileName 값: FILENAME_KEY 이후 ~ GUBUN_KEY 이전 (없으면 끝까지)
    if filename_index != -1:
        filename_start = filename_index + len(FILENAME_KEY)
        filename_end   = gubun_index if gubun_index != -1 else len(url)
        file_name_value = url[filename_start : filename_end]
        return f"{DOWNLOAD_BASE}?pathStr={path_str_value}&fileName={file_name_value}&gubun=cmsfile"

    return f"{DOWNLOAD_BASE}?pathStr={path_str_value}&gubun=cmsfile"


# ── PDF 다운로드 및 텍스트 추출 ───────────────────────────────────

def download_pdf(url: str, save_path: str) -> None:
    """URL에서 PDF를 다운로드해 파일로 저장"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type and len(resp.content) < 100:
        raise ValueError(f"PDF가 아닐 수 있습니다. Content-Type: {content_type}")

    with open(save_path, "wb") as f:
        f.write(resp.content)
    print(f"    다운로드 완료: {len(resp.content):,} bytes → {save_path}")


def extract_pdf_text(pdf_path: str) -> dict:
    """PDF 파일에서 텍스트와 테이블을 추출"""
    result = {"pages": [], "tables": []}

    with pdfplumber.open(pdf_path) as pdf:
        print(f"    총 페이지: {len(pdf.pages)}")

        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            result["pages"].append({"page": i, "text": text})

            tables = page.extract_tables()
            for j, table in enumerate(tables):
                result["tables"].append({"page": i, "table_index": j, "data": table})

    return result


# ── PDF URL 탐지 ──────────────────────────────────────────────────

def find_pdf_urls(html: str, api_data: dict) -> list:
    """
    HTML 콘텐츠와 API 응답에서 PDF URL을 수집.
    1) HTML 내 <a>, <iframe>, <embed> 태그의 href/src 검사
    2) API 응답의 첨부파일 필드(fileList, attachFiles 등) 검사
    """
    soup = BeautifulSoup(html, "html.parser")
    pdf_urls = []

    # HTML 내 링크 탐색
    for tag, attr in [("a", "href"), ("iframe", "src"), ("embed", "src")]:
        for el in soup.find_all(tag, **{attr: True}):
            val = el[attr]
            if ".pdf" in val.lower() or "Download" in val or "pathStr=" in val or "pathStr%3D" in val:
                pdf_urls.append(val)

    # API 응답의 첨부파일 필드 탐색
    for field in ("fileList", "attachFiles", "files", "attachList"):
        items = api_data.get(field) or []
        for item in items:
            for key in ("url", "fileUrl", "filePath", "downloadUrl"):
                val = item.get(key, "")
                if val and (".pdf" in val.lower() or "Download" in val or "pathStr=" in val):
                    if val not in pdf_urls:
                        pdf_urls.append(val)
                    break

    # 상대 경로 → 절대 경로 변환
    absolute = []
    for url in pdf_urls:
        if url.startswith("http"):
            absolute.append(url)
        elif url.startswith("/"):
            absolute.append(BASE_URL + url)
        else:
            absolute.append(BASE_URL + "/" + url)

    # Viewer URL → Download3 URL 변환
    converted = [to_download_url(u) for u in absolute]

    # 중복 제거
    return list(dict.fromkeys(converted))
