#!/usr/bin/env python3
"""
Pre-process markdown files: convert mermaid code blocks to SVG images.
Outputs processed .md files ready for md-bookify PDF conversion.
"""
import subprocess
import sys
import os
import re
import tempfile
import hashlib
from pathlib import Path

MERMAID_BLOCK = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)


def convert_mermaid_to_svg(mermaid_code: str, output_path: str) -> bool:
    """Convert a mermaid diagram to SVG file using mmdc."""
    # Write mermaid code to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
        f.write(mermaid_code)
        mmd_path = f.name

    try:
        result = subprocess.run(
            ['mmdc', '-i', mmd_path, '-o', output_path,
             '-b', 'transparent', '-t', 'neutral'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  mmdc error: {result.stderr}", file=sys.stderr)
            return False
        return True
    finally:
        os.unlink(mmd_path)


def process_file(md_path: Path, svg_dir: Path, output_path: Path):
    """Process one markdown file: convert mermaid blocks to SVG references."""
    content = md_path.read_text(encoding='utf-8')
    name_base = md_path.stem  # e.g. "01-function-calling.zh-CN"

    def replace_mermaid(match):
        mermaid_code = match.group(1).strip()
        code_hash = hashlib.md5(mermaid_code.encode()).hexdigest()[:8]
        svg_filename = f"{name_base}-{code_hash}.svg"
        svg_path = svg_dir / svg_filename

        print(f"  → rendering diagram [{code_hash}]...", end=' ', flush=True)
        if convert_mermaid_to_svg(mermaid_code, str(svg_path)):
            # Use relative path from the output directory
            img_tag = (
                f'<div style="text-align:center; margin:1.5em 0;">\n'
                f'<img src="{svg_filename}" '
                f'alt="Mermaid diagram" '
                f'style="max-width:100%; border:1px solid #e0e0e0; '
                f'border-radius:6px; padding:8px;" />\n'
                f'</div>'
            )
            print("✓")
            return img_tag
        else:
            print("✗ (keeping raw)")
            # Keep original if conversion fails
            return match.group(0)

    processed = MERMAID_BLOCK.sub(replace_mermaid, content)
    output_path.write_text(processed, encoding='utf-8')
    print(f"  wrote {output_path}")


def main():
    docs_dir = Path(__file__).parent.parent.parent / 'docs'
    output_dir = Path(__file__).parent / 'processed'
    svg_dir = output_dir / 'mermaid-svgs'

    output_dir.mkdir(parents=True, exist_ok=True)
    svg_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(docs_dir.glob('*.md'))
    total_diagrams = 0
    successful = 0

    for md_file in md_files:
        print(f"\n📄 {md_file.name}")
        content = md_file.read_text(encoding='utf-8')
        count = len(MERMAID_BLOCK.findall(content))
        total_diagrams += count

        if count > 0:
            print(f"  {count} mermaid diagram(s) found")
        else:
            print(f"  no mermaid diagrams — copying directly")

        process_file(md_file, svg_dir, output_dir / md_file.name)

    # Also count final SVGs
    svgs = list(svg_dir.glob('*.svg'))
    print(f"\n{'='*50}")
    print(f"Total: {len(svgs)} SVG diagrams generated in {svg_dir}")
    print(f"Processed files ready in {output_dir}")


if __name__ == '__main__':
    main()
