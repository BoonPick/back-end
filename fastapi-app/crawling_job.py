from __future__ import annotations
import os
import re
import mysql.connector
from bs4 import BeautifulSoup
from datetime import datetime, date
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://job.sogang.ac.kr"
LOGIN_URL = f"{BASE_URL}/main/login.aspx"
LIST_URL = f"{BASE_URL}/Recruit/RecruitList_Chiup.aspx"
DETAIL_URL = f"{BASE_URL}/Recruit/RecruitView.aspx"
SOURCE_NAME = "sogang_job"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "boonpick"),
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def job_exists(cursor, url: str) -> bool:
    cursor.execute("SELECT id FROM contents WHERE url = %s", (url,))
    return cursor.fetchone() is not None


def save_content(cursor, title: str, url: str, raw_content: str, posted_at=None) -> int:
    if posted_at is not None:
        cursor.execute(
            """
            INSERT INTO contents (title, source_name, category, url, raw_content, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (title, SOURCE_NAME, "job", url, raw_content, posted_at),
        )
    else:
        cursor.execute(
            """
            INSERT INTO contents (title, source_name, category, url, raw_content, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (title, SOURCE_NAME, "job", url, raw_content),
        )
    return cursor.lastrowid


def save_job_posting(cursor, content_id: int, employment: str, work_type: str,
                     duty: str, deadline, is_always_open: int):
    cursor.execute(
        """
        INSERT INTO job_postings (content_id, employment, work_type, duty, deadline, is_always_open)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (content_id, employment, work_type, duty, deadline, is_always_open),
    )


# ── 로그인 ────────────────────────────────────────────────────────

def _login(page):
    saint_id = os.getenv("SAINT_ID", "")
    saint_pw = os.getenv("SAINT_PW", "")
    if not saint_id or not saint_pw:
        raise RuntimeError("SAINT_ID / SAINT_PW 환경변수가 설정되어 있지 않습니다.")

    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

    id_selectors = [
        "input#txtID",
        "input[name*='txtID']",
        "input[placeholder*='아이디']",
        "input[placeholder*='학번']",
        "input[placeholder*='ID']",
        "input[type='text']",
    ]
    pw_selectors = [
        "input#txtPW",
        "input#txtPassword",
        "input[name*='txtPW']",
        "input[name*='Password']",
        "input[placeholder*='비밀번호']",
        "input[type='password']",
    ]

    id_field = None
    for sel in id_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                id_field = el
                break
        except PlaywrightTimeout:
            continue

    pw_field = None
    for sel in pw_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                pw_field = el
                break
        except PlaywrightTimeout:
            continue

    if id_field is None or pw_field is None:
        raise RuntimeError("로그인 폼 입력 필드를 찾지 못했습니다.")

    id_field.fill(saint_id)
    pw_field.fill(saint_pw)

    clicked = False
    for sel in ["input[type='submit']", "button[type='submit']",
                "a:has-text('로그인')", "input[value*='로그인']", "button:has-text('로그인')"]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                clicked = True
                break
        except PlaywrightTimeout:
            continue
    if not clicked:
        page.keyboard.press("Enter")

    try:
        page.wait_for_url(lambda url: "login" not in url.lower(), timeout=10000)
    except PlaywrightTimeout:
        if "login" in page.url.lower():
            raise RuntimeError("로그인 실패 — 학번/비밀번호를 확인하세요.")


# ── HTML 파싱 ─────────────────────────────────────────────────────

def _span_text(soup: BeautifulSoup, span_id: str) -> str:
    el = soup.find("span", id=span_id)
    if not el:
        return ""
    text = el.get_text(strip=True)
    return "" if text == "\xa0" else text


def _parse_deadline(edate_str: str) -> tuple[date | None, int]:
    """
    "2026-05-27 정시" → (date(2026,5,27), 0)
    "상시채용"         → (None, 1)
    """
    if not edate_str or "상시" in edate_str:
        return None, 1
    m = re.search(r"(\d{4}-\d{2}-\d{2})", edate_str)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date(), 0
        except ValueError:
            pass
    return None, 0


def _parse_detail(html: str) -> dict:
    """채용공고 상세 페이지에서 구조화된 필드 추출."""
    soup = BeautifulSoup(html, "html.parser")

    title = _span_text(soup, "Title")
    ru_date = _span_text(soup, "RUDate")        # 등록일: "2026-04-27"
    employment = _span_text(soup, "RecomEmp")   # 채용구분: "인턴"
    work_type = _span_text(soup, "WorkType")    # 근무형태: "인턴직"
    duty = _span_text(soup, "Duty")             # 직무: "기타"
    edate = _span_text(soup, "Edate")           # 마감일: "2026-05-27 정시"

    deadline, is_always_open = _parse_deadline(edate)

    # 본문 텍스트 (ALLTEXT span)
    alltext_el = soup.find("span", id="ALLTEXT")
    if alltext_el:
        for tag in alltext_el(["script", "style"]):
            tag.decompose()
        raw_content = alltext_el.get_text(separator="\n", strip=True)
    else:
        raw_content = ""

    # 등록일 파싱
    posted_at = None
    if ru_date:
        try:
            posted_at = datetime.strptime(ru_date, "%Y-%m-%d")
        except ValueError:
            pass

    return {
        "title": title,
        "employment": employment,
        "work_type": work_type,
        "duty": duty,
        "deadline": deadline,
        "is_always_open": is_always_open,
        "raw_content": raw_content,
        "posted_at": posted_at,
    }


# ── 목록 페이지 ───────────────────────────────────────────────────

def _extract_rcdx_list(html: str) -> list[str]:
    """목록 페이지 HTML에서 rcdx 값 추출."""
    rcdx_set = []
    seen = set()

    soup = BeautifulSoup(html, "html.parser")

    # href 또는 onclick에서 rcdx 파라미터 추출
    pattern = re.compile(r"rcdx=([A-Fa-f0-9]{40,})")

    for tag in soup.find_all(["a", "tr", "td", "span", "div"]):
        for attr in ["href", "onclick"]:
            val = tag.get(attr, "")
            if not val:
                continue
            for m in pattern.finditer(val):
                rcdx = m.group(1)
                if rcdx not in seen:
                    seen.add(rcdx)
                    rcdx_set.append(rcdx)

    return rcdx_set


def _collect_rcdx_all_pages(page, page_count: int) -> list[str]:
    """여러 페이지에서 rcdx 목록 수집."""
    all_rcdx = []

    page.goto(LIST_URL, wait_until="domcontentloaded", timeout=20000)

    for page_num in range(1, page_count + 1):
        print(f"  목록 페이지 {page_num} 수집 중...")
        page.wait_for_load_state("domcontentloaded")

        rcdx_list = _extract_rcdx_list(page.content())
        if not rcdx_list:
            print(f"  페이지 {page_num}: rcdx 없음, 종료")
            break

        all_rcdx.extend(rcdx_list)
        print(f"  {len(rcdx_list)}개 공고 발견 (누적 {len(all_rcdx)}개)")

        if page_num < page_count:
            moved = False
            for sel in [f"a:text-is('{page_num + 1}')", "a:has-text('다음')", "a:has-text('>')"]:
                try:
                    page.click(sel, timeout=3000)
                    page.wait_for_load_state("domcontentloaded")
                    moved = True
                    break
                except PlaywrightTimeout:
                    continue
            if not moved:
                print("  다음 페이지 없음, 종료")
                break

    return all_rcdx


# ── 메인 ─────────────────────────────────────────────────────────

def crawl_jobs(page_count: int = 3) -> int:
    """
    job.sogang.ac.kr 채용공고 크롤링 → contents + job_postings 테이블에 저장.
    SAINT_ID / SAINT_PW 환경변수 필요.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_count = 0

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            print("[sogang_job] 로그인 중...")
            _login(page)
            print("[sogang_job] 로그인 완료")

            rcdx_list = _collect_rcdx_all_pages(page, page_count)
            print(f"\n[sogang_job] 총 {len(rcdx_list)}개 rcdx 수집 완료, 상세 크롤링 시작...")

            for rcdx in rcdx_list:
                detail_url = f"{DETAIL_URL}?rcdx={rcdx}&modalChk=Y"

                if job_exists(cursor, detail_url):
                    print(f"  SKIP (이미 존재): rcdx={rcdx[:16]}...")
                    continue

                try:
                    page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                except PlaywrightTimeout:
                    print(f"  TIMEOUT: {detail_url}")
                    continue

                fields = _parse_detail(page.content())

                if not fields["title"]:
                    print(f"  SKIP (제목 없음): rcdx={rcdx[:16]}...")
                    continue

                content_id = save_content(
                    cursor,
                    title=fields["title"],
                    url=detail_url,
                    raw_content=fields["raw_content"],
                    posted_at=fields["posted_at"],
                )
                save_job_posting(
                    cursor,
                    content_id=content_id,
                    employment=fields["employment"],
                    work_type=fields["work_type"],
                    duty=fields["duty"],
                    deadline=fields["deadline"],
                    is_always_open=fields["is_always_open"],
                )
                conn.commit()
                saved_count += 1

                deadline_label = (
                    fields["deadline"].strftime("%Y-%m-%d") if fields["deadline"]
                    else ("상시채용" if fields["is_always_open"] else "미확인")
                )
                print(f"  SAVED: {fields['title']} | {fields['employment']} | 마감: {deadline_label}")

            browser.close()

    finally:
        cursor.close()
        conn.close()

    print(f"\n[sogang_job] 완료! 총 {saved_count}건 저장됨")
    return saved_count


if __name__ == "__main__":
    crawl_jobs(page_count=3)
