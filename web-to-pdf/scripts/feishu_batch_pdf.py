"""Feishu wiki 트리 전체 → 폴더 구조 + PDF 일괄 생성"""
import asyncio
import json
import sys
import io
import os
import math
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

BASE = "https://seer-group.feishu.cn"


def safe_filename(title):
    """파일명에 사용 불가 문자 제거"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title.strip())
    name = re.sub(r'_+', '_', name).strip('_. ')
    return name[:80] or 'untitled'


async def get_tree(page, root_url):
    """사이드바 API 응답에서 트리 구조 수집"""
    all_nodes = {}
    all_children = {}

    async def on_response(resp):
        try:
            if ("tree/get_info" in resp.url or "tree/get_node" in resp.url) and resp.status == 200:
                body = await resp.text()
                data = json.loads(body)
                if data.get("code") == 0:
                    t = data["data"].get("tree", data["data"])
                    all_nodes.update(t.get("nodes", {}))
                    for p, c in t.get("child_map", {}).items():
                        all_children.setdefault(p, [])
                        for x in c:
                            if x not in all_children[p]:
                                all_children[p].append(x)
        except Exception:
            pass

    page.on("response", on_response)
    await page.goto(root_url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(6000)

    # 사이드바 확장
    for _ in range(3):
        await page.evaluate('''
        () => {
            document.querySelectorAll('[class*="tree-node"], [class*="expand"]').forEach(el => {
                if (el.offsetParent !== null) el.click();
            });
        }
        ''')
        await page.wait_for_timeout(2000)

    page.remove_listener("response", on_response)
    return all_nodes, all_children


def collect_pages(all_nodes, all_children, root_token):
    """DFS로 페이지 목록 수집"""
    result = []

    def dfs(token, depth=0):
        info = all_nodes.get(token, {})
        if info.get("title"):
            result.append({
                "token": token,
                "title": info["title"],
                "url": info.get("url", f"{BASE}/wiki/{token}"),
                "depth": depth,
            })
        for child in all_children.get(token, []):
            dfs(child, depth + 1)

    dfs(root_token)
    return result


async def page_to_pdf(ctx, url, title, pdf_path, png_path):
    """단일 페이지 → PDF 변환"""
    page = await ctx.new_page()

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # lazy-load 스크롤
        prev_height = 0
        for _ in range(30):
            curr_height = await page.evaluate('() => document.body.scrollHeight')
            if curr_height == prev_height:
                break
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(800)
            prev_height = curr_height
        await page.evaluate('window.scrollTo(0, 0)')
        await page.wait_for_timeout(1000)

        # 코드 블록 정리
        await page.evaluate('''
        () => {
            const blocks = document.querySelectorAll(
                '[class*="code-block"], [class*="codeblock"], [class*="CodeBlock"],'
                + '[class*="code_block"], [data-block-type="code"]'
            );
            blocks.forEach(block => {
                block.querySelectorAll(
                    '[class*="toolbar"], [class*="Toolbar"], button, [role="button"],'
                    + '[class*="copy"], [class*="action"], [class*="header"]'
                ).forEach(el => el.remove());
                const codeEl = block.querySelector('code, [class*="line"], pre');
                let text = (codeEl || block).innerText;
                text = text.replace(/^\\s*(Code Block|Plain Text|복사|Copy)\\s*/gim, '').trim();
                const pre = document.createElement('pre');
                const code = document.createElement('code');
                code.textContent = text;
                pre.appendChild(code);
                block.replaceWith(pre);
            });
        }
        ''')

        # Feishu 테이블 병합 (헤더 + 데이터)
        await page.evaluate('''
        () => {
            document.querySelectorAll('.docx-table-inner-wrapper, .table-block').forEach(wrapper => {
                const headerTable = wrapper.querySelector('table.sticky-row-wrapper, table:first-of-type');
                const dataTable = wrapper.querySelector('.content-scroller table');
                if (!headerTable || !dataTable) return;
                const tbody = headerTable.querySelector('tbody') || headerTable;
                Array.from(dataTable.querySelectorAll('tr')).forEach(tr => {
                    tbody.appendChild(tr.cloneNode(true));
                });
                const scroller = wrapper.querySelector('.content-scroller');
                if (scroller) scroller.remove();
                const scrollContainer = wrapper.closest('.scrollable-container');
                if (scrollContainer) scrollContainer.replaceWith(wrapper);
            });
        }
        ''')

        # 본문 HTML 추출
        content_html = await page.evaluate('''
        () => {
            const el = document.querySelector('.bear-web-x-container')
                     || document.querySelector('.docx-container')
                     || document.querySelector('.garr-container')
                     || document.querySelector('.suite-body')
                     || document.querySelector('main');
            return el ? el.outerHTML : '';
        }
        ''')

        if not content_html:
            print(f'    SKIP: no content')
            return False

        # 클린 HTML 페이지 생성
        page2 = await ctx.new_page()
        clean_html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                 'Hiragino Sans GB', 'Microsoft YaHei', Roboto, sans-serif;
    padding: 30px 40px; max-width: 100%; margin: 0 auto;
    color: #1f2329; line-height: 1.7; font-size: 14px;
}}
h1 {{ font-size: 24px; margin-bottom: 20px; }}
h2 {{ font-size: 20px; margin-top: 28px; }}
h3 {{ font-size: 16px; margin-top: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 12px; table-layout: auto; }}
th, td {{ border: 1px solid #dee0e3; padding: 4px 6px; text-align: left; word-break: break-word; font-size: 11px; }}
th {{ background: #f5f6f7; font-weight: 600; }}
pre {{ background: #f5f6f7; border: 1px solid #e0e0e0; border-radius: 6px;
       padding: 14px 16px; overflow-x: auto; line-height: 1.5;
       font-family: 'SF Mono', Consolas, 'Courier New', monospace; font-size: 13px; }}
code {{ font-family: 'SF Mono', Consolas, 'Courier New', monospace; font-size: 13px;
        background: #f5f6f7; padding: 2px 6px; border-radius: 3px; }}
pre code {{ background: none; padding: 0; }}
ul, ol {{ padding-left: 20px; }}
li {{ margin: 4px 0; }}
img {{ max-width: 100%; height: auto; }}
[class*="watermark"], [class*="Watermark"] {{ display: none !important; }}
.bear-web-x-container {{ max-width: 100% !important; padding: 0 !important; }}
</style></head>
<body><h1>{title}</h1>{content_html}</body></html>'''

        await page2.set_content(clean_html, wait_until='load')
        await page2.wait_for_timeout(2000)

        # 스크린샷
        await page2.screenshot(path=png_path, full_page=True)

        # 스크린샷 → A4 PDF (reportlab)
        img = Image.open(png_path)
        img_w, img_h = img.size
        margin = 15 * mm
        a4_w, a4_h = A4
        content_w = a4_w - 2 * margin
        content_h = a4_h - 2 * margin
        scale = content_w / img_w
        src_h_per_page = int(content_h / scale)
        num_pages = math.ceil(img_h / src_h_per_page)

        c = canvas.Canvas(pdf_path, pagesize=A4)
        for i in range(num_pages):
            y_start = i * src_h_per_page
            y_end = min(y_start + src_h_per_page, img_h)
            crop = img.crop((0, y_start, img_w, y_end))
            tmp_path = pdf_path.replace('.pdf', f'_tmp_{i}.png')
            crop.save(tmp_path)
            draw_w = content_w
            draw_h = crop.height * scale
            c.drawImage(tmp_path, margin, a4_h - margin - draw_h,
                        width=draw_w, height=draw_h)
            c.showPage()
            os.remove(tmp_path)
        c.save()

        await page2.close()
        print(f'    PDF: {os.path.getsize(pdf_path):,} bytes, {num_pages} pages')
        return True

    except Exception as e:
        print(f'    ERROR: {e}')
        return False
    finally:
        await page.close()


async def main(root_url, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
            locale='zh-CN', viewport={'width': 1200, 'height': 900},
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")

        # 1) 트리 구조 수집
        print('[1] Fetching tree structure...')
        tree_page = await ctx.new_page()
        all_nodes, all_children = await get_tree(tree_page, root_url)
        await tree_page.close()

        root_token = root_url.rstrip('/').split('/')[-1]
        pages = collect_pages(all_nodes, all_children, root_token)
        print(f'    Found {len(pages)} pages\n')

        # 루트 폴더명
        root_info = all_nodes.get(root_token, {})
        root_title = safe_filename(root_info.get("title", "feishu_wiki"))
        root_dir = os.path.join(output_dir, root_title)
        os.makedirs(root_dir, exist_ok=True)

        # 2) 각 페이지 PDF 생성
        success = 0
        for i, pg in enumerate(pages):
            if pg["token"] == root_token:
                continue  # 루트는 목차 페이지이므로 스킵

            fname = safe_filename(pg["title"])
            pdf_path = os.path.join(root_dir, f'{fname}.pdf')
            png_path = os.path.join(root_dir, f'{fname}.png')

            print(f'[{i}/{len(pages)-1}] {pg["title"]}')

            ok = await page_to_pdf(ctx, pg["url"], pg["title"], pdf_path, png_path)
            if ok:
                success += 1

        await browser.close()

    # 3) 목차 생성
    toc_path = os.path.join(root_dir, '_index.md')
    with open(toc_path, 'w', encoding='utf-8') as f:
        f.write(f'# {root_info.get("title", "Feishu Wiki")}\n\n')
        f.write(f'Source: {root_url}\n\n')
        for pg in pages:
            if pg["token"] == root_token:
                continue
            indent = "  " * (pg["depth"] - 1)
            fname = safe_filename(pg["title"])
            f.write(f'{indent}- [{pg["title"]}]({fname}.pdf)\n')

    print(f'\n[Done] {success}/{len(pages)-1} pages → {root_dir}/')
    print(f'Index: {toc_path}')


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://seer-group.feishu.cn/wiki/LIQlwZE9ZiXKGWkRicLcGNqfnic'
    out = sys.argv[2] if len(sys.argv) > 2 else 'manual/docs/feishu'
    asyncio.run(main(url, out))
