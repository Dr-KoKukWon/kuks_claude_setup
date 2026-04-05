---
name: web-to-pdf
description: "웹 페이지를 PDF로 변환하는 스킬. Playwright 기반 JS 렌더링 + 스크린샷 캡처 + A4 PDF 변환. 단일 페이지, 배치(트리 구조), 일반 웹사이트 모두 지원. 트리거 키워드: 'web to pdf', 'webpage pdf', '웹 pdf', '페이지 pdf', 'url pdf', 'website pdf', 'crawl pdf', 'feishu pdf'"
---

# Web-to-PDF Skill

Playwright 기반 웹 페이지 → PDF 변환 스킬.
JS 렌더링 SPA(Feishu, Notion 등) 포함 모든 웹 페이지를 고품질 PDF로 변환합니다.

## 핵심 기능

| 모드 | 스크립트 | 설명 |
|------|---------|------|
| 단일 페이지 | `web_to_pdf.py` | URL 하나 → PDF 1개 |
| 배치 (Feishu) | `feishu_batch_pdf.py` | Feishu wiki 트리 전체 → 폴더 + PDF |
| 배치 (Sitemap) | `web_to_pdf.py --sitemap` | sitemap.xml 기반 전체 사이트 → PDF |

## 사용법

### 단일 페이지
```bash
python scripts/web_to_pdf.py "https://example.com/page" "output.pdf"
```

### 옵션
```bash
# 뷰포트 크기 지정
python scripts/web_to_pdf.py "URL" "output.pdf" --width 1400 --height 900

# 대기 시간 조절 (JS 렌더링이 느린 사이트)
python scripts/web_to_pdf.py "URL" "output.pdf" --wait 8000

# sitemap 기반 배치
python scripts/web_to_pdf.py "https://docs.example.com" "output_dir/" --sitemap

# CSS 셀렉터로 본문 영역 지정
python scripts/web_to_pdf.py "URL" "output.pdf" --selector "article.content"
```

### Feishu wiki 배치
```bash
python scripts/feishu_batch_pdf.py "https://xxx.feishu.cn/wiki/TOKEN" "output_dir/"
```

## 동작 원리

```
URL 입력
  → Playwright Chromium 로드 (JS 렌더링)
  → 스크롤하여 lazy-load 콘텐츠 로드
  → 불필요 UI 제거 (워터마크, 사이드바, 툴바)
  → 사이트별 특수 처리 (Feishu 테이블 병합, 코드블록 정리 등)
  → 본문 HTML 추출
  → 클린 HTML 페이지 생성 (표준 CSS 적용)
  → 풀페이지 스크린샷 캡처
  → A4 비율 분할 → reportlab PDF 생성
```

## 사이트별 특수 처리

| 사이트 | 처리 내용 |
|--------|----------|
| **Feishu** | sticky-row-wrapper + content-scroller 테이블 병합, 코드블록 UI 제거 |
| **Notion** | 본문 셀렉터 `.notion-page-content` |
| **GitHub** | 본문 셀렉터 `article.markdown-body` |
| **일반 웹** | `article`, `main`, `.content`, `body` 순서로 탐색 |

## 요구사항

```bash
pip install playwright Pillow reportlab
playwright install chromium
```

## 주의사항

1. 인증이 필요한 페이지는 쿠키/토큰 설정 필요
2. 대량 크롤링 시 요청 간격 조절 필요 (기본 2초)
3. 이미지가 많은 페이지는 스크롤 대기 시간 증가 필요 (`--wait`)
4. PDF 파일 크기는 스크린샷 해상도에 비례 (`--width`로 조절)
