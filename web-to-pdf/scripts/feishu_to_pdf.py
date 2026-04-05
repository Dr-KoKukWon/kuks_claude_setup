"""Feishu 페이지 → PDF (HTML 추출 → 클린 페이지 렌더링 → 스크린샷 → PDF)"""
import asyncio
import sys
import io
import os
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright
from PIL import Image


async def save_pdf(url, output_pdf):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
            locale='zh-CN', viewport={'width': 1200, 'height': 900},
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")
        page = await ctx.new_page()

        print(f'Loading {url}...')
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # 끝까지 스크롤하여 lazy-load 콘텐츠 모두 로드
        print('Scrolling to load all content...')
        prev_height = 0
        for _ in range(50):
            curr_height = await page.evaluate('() => document.body.scrollHeight')
            if curr_height == prev_height:
                break
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(800)
            prev_height = curr_height

        await page.evaluate('window.scrollTo(0, 0)')
        await page.wait_for_timeout(1000)

        # 코드 블록 정리: 툴바/버튼 제거, 텍스트만 남기기
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

        # Feishu 테이블 병합: 헤더(sticky-row-wrapper) + 데이터(content-scroller 내 table)를 하나로
        await page.evaluate('''
        () => {
            document.querySelectorAll('.docx-table-inner-wrapper, .table-block').forEach(wrapper => {
                const headerTable = wrapper.querySelector('table.sticky-row-wrapper, table:first-of-type');
                const dataTable = wrapper.querySelector('.content-scroller table');
                if (!headerTable || !dataTable) return;

                // 데이터 테이블의 행을 헤더 테이블로 이동
                const tbody = headerTable.querySelector('tbody') || headerTable;
                Array.from(dataTable.querySelectorAll('tr')).forEach(tr => {
                    tbody.appendChild(tr.cloneNode(true));
                });

                // content-scroller 제거 (이제 헤더 테이블에 모든 행이 있음)
                const scroller = wrapper.querySelector('.content-scroller');
                if (scroller) scroller.remove();

                // scrollable-container 래퍼들도 정리
                const scrollContainer = wrapper.closest('.scrollable-container');
                if (scrollContainer) {
                    scrollContainer.replaceWith(wrapper);
                }
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

        title = await page.evaluate('''
        () => {
            const sels = ['.wiki-title', '[class*="title"] h1', 'h1',
                          '[class*="doc-title"]', '[data-testid="doc-title"]'];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el && el.innerText.trim() && el.innerText.trim() !== '飞书云文档')
                    return el.innerText.trim();
            }
            const c = document.querySelector('.bear-web-x-container, .docx-container, main');
            if (c) { const h = c.querySelector('h1, h2'); if (h) return h.innerText.trim(); }
            return document.title;
        }
        ''')
        print(f'Title: {title}')

        if not content_html:
            print('ERROR: No content found!')
            await browser.close()
            return

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

        # PNG 풀페이지 스크린샷
        print('Taking full-page screenshot...')
        png_path = output_pdf.replace('.pdf', '.png')
        await page2.screenshot(path=png_path, full_page=True)

        await browser.close()

        # 스크린샷 → A4 PDF (reportlab: 이미지 비율 유지하며 페이지 분할)
        print('Generating PDF from screenshot...')
        os.makedirs(os.path.dirname(output_pdf) or '.', exist_ok=True)

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        img = Image.open(png_path)
        img_w, img_h = img.size

        margin = 15 * mm
        a4_w, a4_h = A4  # 595.27, 841.89 points
        content_w = a4_w - 2 * margin
        content_h = a4_h - 2 * margin

        # 이미지를 content 너비에 비율 맞춤
        scale = content_w / img_w
        # 원본 이미지에서 한 페이지에 들어갈 높이 (원본 px 기준)
        src_h_per_page = int(content_h / scale)

        num_pages = math.ceil(img_h / src_h_per_page)
        print(f'Screenshot: {img_w}x{img_h}, scale: {scale:.3f}, pages: {num_pages}')

        c = canvas.Canvas(output_pdf, pagesize=A4)

        for i in range(num_pages):
            y_start = i * src_h_per_page
            y_end = min(y_start + src_h_per_page, img_h)
            crop = img.crop((0, y_start, img_w, y_end))

            # 크롭 이미지를 임시 저장
            tmp_path = output_pdf.replace('.pdf', f'_tmp_{i}.png')
            crop.save(tmp_path)

            draw_w = content_w
            draw_h = crop.height * scale
            # PDF 좌표는 좌하단 기준, 이미지를 상단부터 배치
            c.drawImage(tmp_path, margin, a4_h - margin - draw_h,
                        width=draw_w, height=draw_h)
            c.showPage()
            os.remove(tmp_path)

        c.save()

        pdf_size = os.path.getsize(output_pdf)
        png_size = os.path.getsize(png_path)
        print(f'PDF: {output_pdf} ({pdf_size:,} bytes, {num_pages} pages)')
        print(f'PNG: {png_path} ({png_size:,} bytes)')


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://seer-group.feishu.cn/wiki/OldKwqjGRijFgjkwikHcUxmVnpg'
    out = sys.argv[2] if len(sys.argv) > 2 else 'docs/feishu_stop_openloop.pdf'
    asyncio.run(save_pdf(url, out))
