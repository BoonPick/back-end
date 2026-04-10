import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import re

SAINT_ID = "20241630"   # 직접 입력
SAINT_PW = "chan2005!"   # 직접 입력

async def crawl_sogang_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # ✅ alert/confirm/prompt 자동 수락
        async def handle_dialog(dialog):
            print(f"   [팝업 자동처리] {dialog.message}")
            await dialog.accept()
        page.on("dialog", handle_dialog)

        # 1. 로그인
        print("🔐 로그인 중...")
        await page.goto("https://job.sogang.ac.kr/main/login.aspx")
        await page.wait_for_load_state("networkidle")
        await page.fill('input[name="rUserid"]', SAINT_ID)
        await page.fill('input[name="rPW"]', SAINT_PW)
        await page.press('input[name="rPW"]', 'Enter')
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        print("✅ 로그인 완료")

        list_url = "https://job.sogang.ac.kr/recruit/RecruitList.aspx"
        await page.goto(list_url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)

        jobs = []
        page_num = 1

        while True:
            print(f"📄 {page_num}페이지 수집 중...")
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            anchors = soup.select("a[href*='detailView']")
            if not anchors:
                print("⚠️ 공고 링크를 찾지 못했습니다.")
                break

            # hash, id 추출
            detail_items = []
            for anchor in anchors:
                href = anchor.get("href", "")
                title = anchor.get_text(strip=True)
                match = re.search(r"detailView\('([^']+)',\s*'([^']+)'\)", href)
                if match:
                    detail_items.append({
                        "title": title,
                        "hash": match.group(1),
                        "id": match.group(2)
                    })

            print(f"   → {len(detail_items)}개 공고 발견")

            for item in detail_items:
                try:
                    # ✅ detailView 대신 URL 직접 구성
                    detail_url = (
                        f"https://job.sogang.ac.kr/recruit/RecruitView.aspx"
                        f"?rcdx={item['hash']}&modalChk=Y"
                    )
                    await page.goto(detail_url)
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1)

                    current_url = page.url
                    detail_html = await page.content()
                    detail_soup = BeautifulSoup(detail_html, "html.parser")

                    def get_span(s, span_id):
                        el = s.find("span", id=span_id)
                        return el.get_text(strip=True) if el else ""

                    근무형태 = get_span(detail_soup, "WorkType")
                    마감일   = get_span(detail_soup, "Edate")
                    직무     = get_span(detail_soup, "Duty")

                    # 제목은 링크 텍스트 사용
                    제목 = item["title"]

                    job = {
                        "제목":    제목,
                        "근무형태": 근무형태,
                        "마감일":  마감일,
                        "직무":    직무,
                        "링크":    current_url,
                    }
                    jobs.append(job)
                    print(f"   ✔ {제목} | {근무형태} | {마감일} | {직무}")

                except Exception as e:
                    print(f"   ⚠️ 오류 ({item['title']}): {e}")

            # 다음 페이지
            await page.goto(list_url)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)

            if page_num > 1:
                for _ in range(page_num - 1):
                    nb = page.locator("a:has-text('다음')")
                    if await nb.count() > 0:
                        await nb.click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(0.5)

            next_btn = page.locator("a:has-text('다음')")
            if await next_btn.count() == 0:
                print("✅ 마지막 페이지 도달")
                break

            await next_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            page_num += 1

        await browser.close()

        if not jobs:
            print("❌ 수집된 공고가 없습니다.")
            return

        filename = f"sogang_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"서강대학교 취업공고\n")
            f.write(f"수집일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"총 {len(jobs)}개\n")
            f.write("=" * 60 + "\n\n")
            for i, job in enumerate(jobs, 1):
                f.write(f"[{i}]\n")
                f.write(f"제목     : {job['제목']}\n")
                f.write(f"근무형태 : {job['근무형태']}\n")
                f.write(f"마감일   : {job['마감일']}\n")
                f.write(f"직무     : {job['직무']}\n")
                f.write(f"링크     : {job['링크']}\n")
                f.write("-" * 60 + "\n\n")

        print(f"\n🎉 총 {len(jobs)}개 저장 완료! → {filename}")

if __name__ == "__main__":
    asyncio.run(crawl_sogang_jobs())