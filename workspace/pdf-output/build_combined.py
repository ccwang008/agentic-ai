#!/usr/bin/env python3
"""
Build a single combined markdown file with Table of Contents
from processed chapter files. Output: combined.md
"""
import re
import sys
from pathlib import Path

def extract_title(md_text: str) -> str:
    """Extract first h1 heading."""
    for line in md_text.split('\n'):
        line = line.strip()
        if line.startswith('# ') and not line.startswith('## '):
            return line[2:].strip()
    return None

def extract_h2_headings(md_text: str) -> list[str]:
    """Extract all h2 headings."""
    headings = []
    for line in md_text.split('\n'):
        line = line.strip()
        if line.startswith('## '):
            headings.append(line[3:].strip())
    return headings

def build_toc(chapters: list[tuple[str, str, str]]) -> str:
    """Build a plain-text Table of Contents (no markdown links — PDF-ready)."""
    lines = [
        '# 目录',
        '',
    ]
    for idx, (filename, title, _content) in enumerate(chapters, 1):
        # Extract clean title without # markers
        clean = title.replace('# ', '').strip()
        lines.append(f'{idx}.&emsp;{clean}')

    lines.append('')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines)

def main():
    processed_dir = Path(__file__).parent / 'processed'
    output_path = processed_dir / 'combined.md'

    chapters = []
    for md_file in sorted(processed_dir.glob('??-*.md')):
        content = md_file.read_text(encoding='utf-8')
        title = extract_title(content)
        if title:
            chapters.append((md_file.name, title, content))
            print(f'  {md_file.name}: {title}')

    print(f'\nTotal: {len(chapters)} chapters')

    # Build combined file
    parts = []
    # Title page
    parts.append('# 生产级 Agentic 系统 —— 课程讲义')
    parts.append('')
    parts.append('> 原课程：Production-grade agentic systems')
    parts.append('>')
    parts.append('> 中译本，含完整流程图和代码示例')
    parts.append('')
    parts.append('---')
    parts.append('')

    # Table of Contents
    parts.append(build_toc(chapters))

    # All chapters
    for filename, title, content in chapters:
        parts.append(content)
        parts.append('')
        parts.append('<div style="page-break-after:always;"></div>')
        parts.append('')

    combined = '\n'.join(parts)
    output_path.write_text(combined, encoding='utf-8')
    print(f'\nWritten: {output_path} ({len(combined)} chars)')

if __name__ == '__main__':
    main()
