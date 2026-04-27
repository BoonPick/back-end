import os
import mysql.connector
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://job.sogang.ac.kr"
LOGIN_URL = f"{BASE_URL}/main/login.aspx"
LIST_URL = f"{BASE_URL}/Recruit/RecruitList_Chiup.aspx"
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


def save_job(cursor, title: str, url: str, raw_content: str, posted_at=None):
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


def _parse_date(date_str: str):
    if not date_str:
        return None
    cleaned = date_str.strip().replace(".", "-")[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


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

    submit_selectors = [
        "input[type='submit']",
        "button[type='submit']",
        "a:has-text('로그인')",
        "input[value*='로그인']",
        "button:has-text('로그인')",
    ]
    clicked = False
    for sel in submit_selectors:
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


def _extract_listings(html: str) -> list[dict]:
    """Extract job listings from list page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    rows = soup.select("table tbody tr") or soup.select("table tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        title_link = None
        for cell in cells:
            a = cell.find("a", href=True)
            if a and a.get_text(strip=True):
                title_link = a
                break

        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        if not title:
            continue

        href = title_link["href"]
        if href.startswith("http"):
            detail_url = href
        elif href.startswith("/"):
            detail_url = BASE_URL + href
        else:
            detail_url = BASE_URL + "/Recruit/" + href

        date_str = ""
        for cell in cells:
            text = cell.get_text(strip=True)
            # Looks like a date: starts with 4-digit year, contains separator
            if len(text) >= 8 and text[:4].isdigit() and any(c in text for c in ["-", "."]):
                date_str = text[:10]
                break

        jobs.append({"title": title, "url": detail_url, "date_str": date_str})

    return jobs


def _collect_all_listings(page, page_count: int) -> list[dict]:
    """Navigate list pages and collect all job entries."""
    all_jobs = []

    page.goto(LIST_URL, wait_until="domcontentloaded", timeout=20000)

    for page_num in range(1, page_count + 1):
        print(f"  목록 페이지 {page_num} 수집 중...")
        page.wait_for_load_state("domcontentloaded")

        jobs = _extract_listings(page.content())
        if not jobs:
            print(f"  페이지 {page_num}: 공고 없음, 종료")
            break

        all_jobs.extend(jobs)
        print(f"  {len(jobs)}개 공고 발견 (누적 {len(all_jobs)}개)")

        if page_num < page_count:
            moved = False
            next_str = str(page_num + 1)
            for sel in [f"a:text-is('{next_str}')", "a:has-text('다음')", "a:has-text('>')"]:
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

    return all_jobs


def _fetch_detail(page, url: str) -> tuple[str, str | None]:
    """Fetch detail page and return (raw_content, date_str)."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except PlaywrightTimeout:
        return "", None

    soup = BeautifulSoup(page.content(), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    body = (
        soup.find("div", class_=lambda c: c and "content" in c.lower())
        or soup.find("div", id=lambda i: i and "content" in i.lower())
        or soup.find("body")
    )
    raw_content = body.get_text(separator="\n", strip=True) if body else ""

    date_str = None
    for text_node in soup.find_all(string=True):
        text = text_node.strip()
        if len(text) >= 8 and text[:4].isdigit() and ("." in text or "-" in text):
            date_str = text[:10]
            break

    return raw_content, date_str


def crawl_jobs(page_count: int = 3) -> int:
    """
    Crawl job postings from job.sogang.ac.kr and save to DB.
    Requires SAINT_ID and SAINT_PW environment variables.
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

            listings = _collect_all_listings(page, page_count)
            print(f"\n[sogang_job] 총 {len(listings)}개 공고 수집 완료, 상세 크롤링 시작...")

            for job in listings:
                if job_exists(cursor, job["url"]):
                    print(f"  SKIP (이미 존재): {job['title']}")
                    continue

                raw_content, detail_date = _fetch_detail(page, job["url"])
                date_str = detail_date or job.get("date_str", "")
                posted_at = _parse_date(date_str)

                save_job(cursor, job["title"], job["url"], raw_content, posted_at=posted_at)
                conn.commit()
                saved_count += 1
                date_label = posted_at.strftime("%Y-%m-%d") if posted_at else "날짜 미확인"
                print(f"  SAVED: {job['title']} ({date_label})")

            browser.close()

    finally:
        cursor.close()
        conn.close()

    print(f"\n[sogang_job] 완료! 총 {saved_count}건 저장됨")
    return saved_count


if __name__ == "__main__":
    crawl_jobs(page_count=3)
