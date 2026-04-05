"""범용 웹 페이지 → PDF 변환 (Playwright 스크린샷 기반)

Usage:
    python web_to_pdf.py "https://example.com" "output.pdf"
    python web_to_pdf.py "https://example.com" "output.pdf" --selector "article"
    python web_to_pdf.py "https://docs.example.com" "output_dir/" --sitemap
"""
import asyncio
import argparse
import json
import sys
import io
import os
import re
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.async_api import async_playwright
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas


# ── 사이트별 설정 ──────────────────────────────────────────────

SITE_CONFIGS = {
    'feishu.cn': {
        'selectors': ['.bear-web-x-container', '.docx-container', '.garr-container',
                       '.suite-body', 'main'],
        'hide': ['[class*="watermark"]', '[class*="Watermark"]',
                 '[class*="sidebar"]', '[class*="Sidebar"]',
                 '[class*="catalog"]', '[class*="comment"]',
                 '.suite-header', '[class*="banner"]', '[class*="footer"]',
                 '[class*="tooltip"]'],
        'pre_extract': 'feishu',
    },
    'notion.so': {
        'selectors': ['.notion-page-content', 'main', 'article'],
        'hide': ['[class*="sidebar"]', 'header', 'nav', '[class*="topbar"]'],
    },
    'notion.site': {
        'selectors': ['.notion-page-content', 'main', 'article'],
        'hide': ['[class*="sidebar"]', 'header', 'nav', '[class*="topbar"]'],
    },
    'github.com': {
        'selectors': ['article.markdown-body', 'main', 'article'],
        'hide': ['header', 'nav', '.footer', '[class*="sidebar"]',
                 '.js-header-wrapper'],
    },
    'default': {
        'selectors': ['article', 'main', '.content', '.post-content',
                       '#content', '.entry-content', 'body'],
        'hide': ['header', 'nav', 'footer', '[class*="sidebar"]',
                 '[class*="cookie"]', '[class*="popup"]', '[class*="modal"]',
                 '[class*="banner"]', '[class*="ad-"]'],
    },
}

FEISHU_PRE_EXTRACT_JS = '''
() => {
    // 코드 블록: 툴바/버튼 제거, 텍스트만 pre/code로 치환
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

    // 테이블 병합: 헤더(sticky-row-wrapper) + 데이터(content-scroller)
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
'''


def get_site_config(url):
    for domain, cfg in SITE_CONFIGS.items():
        if domain != 'default' and domain in url:
            return cfg
    return SITE_CONFIGS['default']


def safe_filename(title):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\u200b]', '_', title.strip())
    name = re.sub(r'_+', '_', name).strip('_. ')
    return name[:80] or 'untitled'


def screenshot_to_pdf(png_path, pdf_path):
    """스크린샷 PNG → A4 PDF 변환 (reportlab)"""
    img = Image.open(png_path)
    img_w, img_h = img.size
    margin = 15 * mm
    a4_w, a4_h = A4
    content_w = a4_w - 2 * margin
    content_h = a4_h - 2 * margin
    scale = content_w / img_w
    src_h_per_page = int(content_h / scale)
    num_pages = math.ceil(img_h / src_h_per_page)

    c = rl_canvas.Canvas(pdf_path, pagesize=A4)
    for i in range(num_pages):
        y_start = i * src_h_per_page
        y_end = min(y_start + src_h_per_page, img_h)
        crop = img.crop((0, y_start, img_w, y_end))
        tmp = pdf_path.replace('.pdf', f'_tmp_{i}.png')
        crop.save(tmp)
        draw_w = content_w
        draw_h = crop.height * scale
        c.drawImage(tmp, margin, a4_h - margin - draw_h,
                    width=draw_w, height=draw_h)
        c.showPage()
        os.remove(tmp)
    c.save()
    return num_pages


CLEAN_HTML_TEMPLATE = '''<!DOCTYPE html>
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
       font-family: 'SF Mono', Consolas, 'Courier New', monospace; font-size: 13px;
       white-space: pre-wrap; word-break: break-all; }}
code {{ font-family: 'SF Mono', Consolas, 'Courier New', monospace; font-size: 13px;
        background: #f5f6f7; padding: 2px 6px; border-radius: 3px; }}
pre code {{ background: none; padding: 0; }}
ul, ol {{ padding-left: 20px; }}
li {{ margin: 4px 0; }}
img {{ max-width: 100%; height: auto; }}
[class*="watermark"], [class*="Watermark"] {{ display: none !important; }}
</style></head>
<body><h1>{title}</h1>{content}</body></html>'''


async def convert_page(ctx, url, pdf_path, png_path, selector=None,
                       wait_ms=5000, site_cfg=None):
    """단일 페이지 → PDF 변환"""
    page = await ctx.new_page()

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(wait_ms)

        # lazy-load 스크롤
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

        cfg = site_cfg or get_site_config(url)

        # 사이트별 전처리
        if cfg.get('pre_extract') == 'feishu':
            await page.evaluate(FEISHU_PRE_EXTRACT_JS)

        # 불필요 UI 숨기기
        hide_sels = cfg.get('hide', [])
        if hide_sels:
            await page.evaluate('''
            (sels) => {
                sels.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        el.style.setProperty('display', 'none', 'important');
                    });
                });
            }
            ''', hide_sels)

        # 본문 HTML 추출
        content_sels = [selector] if selector else cfg.get('selectors', ['body'])
        content_html = await page.evaluate('''
        (sels) => {
            for (const sel of sels) {
                const el = document.querySelector(sel);
                if (el && el.innerText.trim().length > 50) return el.outerHTML;
            }
            return document.body.outerHTML;
        }
        ''', content_sels)

        # 제목 추출
        title = await page.evaluate('''
        () => {
            const sels = ['.wiki-title', 'h1', '[class*="title"] h1',
                          '[class*="doc-title"]', 'title'];
            for (const s of sels) {
                const el = document.querySelector(s);
                const t = el ? el.innerText.trim() : '';
                if (t && t.length < 200) return t;
            }
            return document.title || 'Untitled';
        }
        ''')
        title = title.replace('\u200b', '').strip()

        if not content_html or len(content_html) < 100:
            print(f'    SKIP: no content')
            return None

        # 클린 HTML 페이지
        page2 = await ctx.new_page()
        clean_html = CLEAN_HTML_TEMPLATE.format(title=title, content=content_html)
        await page2.set_content(clean_html, wait_until='load')
        await page2.wait_for_timeout(2000)

        # 스크린샷
        await page2.screenshot(path=png_path, full_page=True)
        await page2.close()

        # PDF 생성
        num_pages = screenshot_to_pdf(png_path, pdf_path)

        return {'title': title, 'pages': num_pages,
                'size': os.path.getsize(pdf_path)}

    except Exception as e:
        print(f'    ERROR: {e}')
        return None
    finally:
        await page.close()


async def batch_from_sitemap(base_url, output_dir, args):
    """sitemap.xml 기반 배치 변환"""
    import xml.etree.ElementTree as ET
    import requests

    os.makedirs(output_dir, exist_ok=True)

    sitemap_url = base_url.rstrip('/') + '/sitemap.xml'
    print(f'Fetching sitemap: {sitemap_url}')
    try:
        resp = requests.get(sitemap_url, timeout=10)
        root = ET.fromstring(resp.content)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [loc.text for loc in root.findall('.//sm:loc', ns)]
    except Exception as e:
        print(f'Sitemap fetch failed: {e}')
        return

    if not urls:
        print('No URLs found.')
        return

    print(f'Found {len(urls)} URLs\n')

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
            locale='zh-CN', viewport={'width': args.width, 'height': args.height},
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")

        success = 0
        for i, url in enumerate(urls):
            slug = safe_filename(url.split('/')[-1] or f'page_{i}')
            pdf_path = os.path.join(output_dir, f'{slug}.pdf')
            png_path = os.path.join(output_dir, f'{slug}.png')

            print(f'[{i+1}/{len(urls)}] {url}')
            result = await convert_page(ctx, url, pdf_path, png_path,
                                        selector=args.selector, wait_ms=args.wait)
            if result:
                success += 1
                print(f'    {result["size"]:,} bytes, {result["pages"]} pages')
            await asyncio.sleep(2)

        await browser.close()
    print(f'\n[Done] {success}/{len(urls)} pages -> {output_dir}/')


async def single_page(url, output_pdf, args):
    """단일 URL → PDF"""
    os.makedirs(os.path.dirname(output_pdf) or '.', exist_ok=True)
    png_path = output_pdf.replace('.pdf', '.png')

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
            locale='zh-CN', viewport={'width': args.width, 'height': args.height},
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")

        print(f'Converting: {url}')
        result = await convert_page(ctx, url, output_pdf, png_path,
                                    selector=args.selector, wait_ms=args.wait)
        await browser.close()

        if result:
            print(f'Title: {result["title"]}')
            print(f'PDF: {output_pdf} ({result["size"]:,} bytes, {result["pages"]} pages)')
            print(f'PNG: {png_path}')
        else:
            print('Failed to convert page.')


def main():
    parser = argparse.ArgumentParser(description='Web page to PDF converter')
    parser.add_argument('url', help='URL to convert')
    parser.add_argument('output', help='Output PDF path or directory (with --sitemap)')
    parser.add_argument('--sitemap', action='store_true', help='Batch: crawl sitemap.xml')
    parser.add_argument('--selector', default=None, help='CSS selector for content area')
    parser.add_argument('--width', type=int, default=1200, help='Viewport width (default: 1200)')
    parser.add_argument('--height', type=int, default=900, help='Viewport height (default: 900)')
    parser.add_argument('--wait', type=int, default=5000, help='Wait ms after page load (default: 5000)')

    args = parser.parse_args()

    if args.sitemap:
        asyncio.run(batch_from_sitemap(args.url, args.output, args))
    else:
        asyncio.run(single_page(args.url, args.output, args))


if __name__ == '__main__':
    main()
