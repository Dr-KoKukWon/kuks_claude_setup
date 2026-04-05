# web-to-pdf

Claude Code skill for converting web pages to PDF.

Playwright-based web page to PDF converter supporting JS-rendered SPA pages (Feishu, Notion, GitHub, etc.)

## Features

- **Single page**: Any URL to A4 PDF
- **Batch (Feishu)**: Feishu wiki tree to folder structure with PDFs
- **Batch (Sitemap)**: sitemap.xml-based site-wide PDF generation
- **JS rendering**: Full Chromium rendering via Playwright
- **Smart extraction**: Site-specific content selectors and preprocessing
- **Clean output**: Removes watermarks, sidebars, toolbars, ads

## Installation

### As Claude Code Skill

```bash
# Copy to skills directory
cp -r web-to-pdf ~/.claude/skills/

# Install dependencies
pip install playwright Pillow reportlab
playwright install chromium
```

### Add to CLAUDE.md

```markdown
# Web-to-PDF Skill
- Skill path: `~/.claude/skills/web-to-pdf/`
- Trigger keywords: "web to pdf", "webpage pdf", "url pdf", "feishu pdf"
- Usage: Read SKILL.md and follow workflow
```

## Quick Start

```bash
# Single page
python scripts/web_to_pdf.py "https://example.com" "output.pdf"

# Feishu wiki tree
python scripts/feishu_batch_pdf.py "https://xxx.feishu.cn/wiki/TOKEN" "output/"

# Site-wide via sitemap
python scripts/web_to_pdf.py "https://docs.example.com" "output/" --sitemap
```

## Requirements

- Python 3.10+
- playwright, Pillow, reportlab

## License

MIT
