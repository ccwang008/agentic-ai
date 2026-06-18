# Chinese Agentic Systems Course PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one polished, navigable Chinese PDF from the 23 translated Markdown chapters Ch.00-Ch.22.

**Architecture:** A Python orchestrator validates and combines the source Markdown, asks Pandoc for semantic HTML, and prints it through Chromium after rendering Mermaid blocks in-browser. A second pass discovers the real chapter start pages, fills the fixed-size table of contents, overlays running headers and page numbers, and writes PDF outlines with pypdf.

**Tech Stack:** Python 3, pytest, Pandoc, Playwright/Chromium, Mermaid 11 browser bundle, pdfplumber, pypdf, ReportLab, Poppler.

---

## File map

- Create `workspace/course-pdf/build_pdf.py`: source validation, Markdown/HTML transformation, browser printing, two-pass TOC, page overlays, bookmarks, and CLI.
- Create `workspace/course-pdf/book.css`: A4 typography, chapter/TOC page breaks, code, table, and Mermaid styling.
- Create `workspace/course-pdf/tests/test_build_pdf.py`: deterministic unit tests for discovery, chapter parsing, HTML markers, and page-number conversion.
- Create `workspace/course-pdf/verify_pdf.py`: structural and visual QA report.
- Download `workspace/course-pdf/vendor/mermaid.min.js`: pinned Mermaid browser renderer.
- Produce `output/pdf/production-grade-agentic-systems-zh-CN.pdf`: final deliverable.
- Use `tmp/pdfs/course-book/`: disposable combined Markdown, HTML, first-pass PDF, overlays, and rendered page PNGs.

### Task 1: Source manifest and chapter metadata

**Files:**
- Create: `workspace/course-pdf/tests/test_build_pdf.py`
- Create: `workspace/course-pdf/build_pdf.py`

- [ ] **Step 1: Write failing manifest tests**

```python
from pathlib import Path
from build_pdf import Chapter, discover_chapters, printed_page


def test_discovers_all_translations_in_numeric_order(tmp_path: Path):
    for number in (2, 0, 1):
        (tmp_path / f"{number:02d}-chapter.zh-CN.md").write_text(
            f"# 第 {number:02d} 章 - 标题 {number}\n\n正文", encoding="utf-8"
        )
    chapters = discover_chapters(tmp_path)
    assert [chapter.number for chapter in chapters] == [0, 1, 2]


def test_rejects_missing_or_duplicate_chapter_numbers(tmp_path: Path):
    (tmp_path / "00-a.zh-CN.md").write_text("# A", encoding="utf-8")
    (tmp_path / "02-b.zh-CN.md").write_text("# B", encoding="utf-8")
    try:
        discover_chapters(tmp_path)
    except ValueError as exc:
        assert "expected Ch.00-Ch.22" in str(exc)
    else:
        raise AssertionError("missing chapter must fail")


def test_printed_page_excludes_cover_and_two_toc_pages():
    assert printed_page(3) == 1
    assert printed_page(25) == 23
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `cd workspace/course-pdf && python -m pytest tests/test_build_pdf.py -q`

Expected: import failure because `build_pdf.py` does not exist.

- [ ] **Step 3: Implement the source model and strict discovery**

```python
@dataclass(frozen=True)
class Chapter:
    number: int
    path: Path
    title: str
    markdown: str


def discover_chapters(source_dir: Path) -> list[Chapter]:
    paths = sorted(source_dir.glob("[0-2][0-9]-*.zh-CN.md"))
    chapters = [parse_chapter(path) for path in paths]
    numbers = [chapter.number for chapter in chapters]
    if numbers != list(range(23)):
        raise ValueError(f"expected Ch.00-Ch.22 exactly once, got {numbers}")
    return chapters


def parse_chapter(path: Path) -> Chapter:
    number = int(path.name[:2])
    markdown = path.read_text(encoding="utf-8")
    first_heading = next(
        (line[2:].strip() for line in markdown.splitlines() if line.startswith("# ")),
        None,
    )
    if not first_heading:
        raise ValueError(f"missing H1 in {path}")
    return Chapter(number, path, first_heading, markdown)


def printed_page(physical_zero_based_page: int) -> int:
    return physical_zero_based_page - 2
```

- [ ] **Step 4: Run tests and validate the real manifest**

Run: `cd workspace/course-pdf && python -m pytest tests/test_build_pdf.py -q`

Expected: all tests pass.

Run: `python workspace/course-pdf/build_pdf.py --check-sources docs`

Expected: `23 chapters: Ch.00-Ch.22`.

### Task 2: Semantic HTML and print stylesheet

**Files:**
- Modify: `workspace/course-pdf/tests/test_build_pdf.py`
- Modify: `workspace/course-pdf/build_pdf.py`
- Create: `workspace/course-pdf/book.css`

- [ ] **Step 1: Write failing transformation tests**

```python
from build_pdf import build_combined_markdown, render_html


def test_combined_markdown_has_stable_chapter_markers():
    chapter = Chapter(7, Path("07-memory.zh-CN.md"), "第 07 章 - 记忆", "# 第 07 章 - 记忆\n正文")
    combined = build_combined_markdown([chapter], {7: 42})
    assert 'id="chapter-07"' in combined
    assert 'data-marker="CHAPTER_START_07"' in combined
    assert "第 07 章 - 记忆" in combined


def test_html_preserves_code_language_and_mermaid_blocks(tmp_path: Path):
    source = "```python\nprint('ok')\n```\n\n```mermaid\nflowchart LR\nA-->B\n```"
    html = render_html(source, tmp_path / "book.html", Path("book.css"))
    assert 'class="sourceCode python"' in html
    assert 'class="mermaid"' in html
```

- [ ] **Step 2: Run tests and confirm the new assertions fail**

Run: `cd workspace/course-pdf && python -m pytest tests/test_build_pdf.py -q`

Expected: failures for undefined transformation functions.

- [ ] **Step 3: Implement combined Markdown and Pandoc HTML generation**

`build_combined_markdown()` must emit, in order: cover section; two fixed TOC pages containing 12 and 11 chapter rows; then 23 chapter sections. Each chapter section starts with a visible H1 anchor and a 1pt white marker text used only for reliable page discovery. `render_html()` must run:

```bash
pandoc combined.md --from=gfm+fenced_divs --to=html5 --standalone \
  --highlight-style=pygments --css=book.css --output=book.html
```

After Pandoc, replace each `<pre class="mermaid"><code>...</code></pre>` wrapper with `<div class="mermaid">...</div>` while HTML-unescaping only the code contents. Fail if input and output Mermaid counts differ.

- [ ] **Step 4: Add the A4 stylesheet**

Use these fixed print constraints in `book.css`:

```css
@page { size: A4; margin: 19mm 18mm 20mm 20mm; }
html { font-size: 10.5pt; }
body { font-family: "PingFang SC", "Hiragino Sans GB", sans-serif; color: #18212f; line-height: 1.68; }
.cover { page: cover; break-after: page; height: 240mm; display: grid; place-content: center; text-align: center; }
.toc-page { break-after: page; }
.chapter { break-before: page; }
h1, h2, h3 { color: #15324b; break-after: avoid-page; }
h1 { font-size: 25pt; border-bottom: 2px solid #4d7c8a; padding-bottom: 8mm; }
h2 { font-size: 17pt; margin-top: 1.4em; }
h3 { font-size: 13pt; margin-top: 1.2em; }
pre { font-family: Menlo, Monaco, monospace; font-size: 8.1pt; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f6f8; border-left: 3px solid #6f97a5; padding: 10px 12px; break-inside: avoid-page; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; break-inside: avoid-page; }
th, td { border: 1px solid #ccd5dc; padding: 5px 7px; vertical-align: top; }
.mermaid { display: flex; justify-content: center; break-inside: avoid-page; margin: 1.2em 0; }
.mermaid svg { max-width: 100%; max-height: 225mm; }
.chapter-marker { color: white; font-size: 1pt; line-height: 1pt; }
```

- [ ] **Step 5: Run tests and inspect HTML invariants**

Run: `cd workspace/course-pdf && python -m pytest tests/test_build_pdf.py -q`

Expected: all tests pass.

Run: `python workspace/course-pdf/build_pdf.py --html-only`

Expected: reports 23 chapters, 40 Mermaid blocks, and 107 total fenced code blocks without mismatch.

### Task 3: Mermaid rendering and Chromium printing

**Files:**
- Create: `workspace/course-pdf/vendor/mermaid.min.js`
- Modify: `workspace/course-pdf/build_pdf.py`

- [ ] **Step 1: Download and pin Mermaid 11**

Run: `curl -L https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.min.js -o workspace/course-pdf/vendor/mermaid.min.js`

Expected: HTTP success and a non-empty JavaScript file.

- [ ] **Step 2: Implement browser rendering with explicit failure capture**

`print_html()` must launch bundled Playwright Chromium, open the local HTML, inject the local Mermaid bundle, and execute:

```javascript
mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
const nodes = [...document.querySelectorAll(".mermaid")];
await mermaid.run({ nodes });
return {
  total: nodes.length,
  rendered: nodes.filter(node => node.querySelector("svg")).length,
  errors: [...document.querySelectorAll(".error-icon")].length
};
```

Abort unless the result is `{total: 40, rendered: 40, errors: 0}`. Then call Playwright `page.pdf()` with A4 format, backgrounds enabled, CSS page size preferred, and zero browser margins because CSS owns the margins.

- [ ] **Step 3: Generate and inspect first-pass PDF metadata**

Run: `python workspace/course-pdf/build_pdf.py --first-pass`

Expected: `tmp/pdfs/course-book/first-pass.pdf` exists, has more than 100 pages, and `pdfinfo` reports A4 page size.

### Task 4: Accurate TOC, running matter, and bookmarks

**Files:**
- Modify: `workspace/course-pdf/tests/test_build_pdf.py`
- Modify: `workspace/course-pdf/build_pdf.py`

- [ ] **Step 1: Write failing marker and outline tests**

```python
from build_pdf import chapter_pages_from_text


def test_chapter_markers_map_to_first_physical_page():
    pages = ["cover", "toc", "toc", "CHAPTER_START_00 body", "x", "CHAPTER_START_01"]
    assert chapter_pages_from_text(pages) == {0: 3, 1: 5}
```

- [ ] **Step 2: Implement two-pass page discovery**

Use pdfplumber to extract every first-pass page. `chapter_pages_from_text()` must find each `CHAPTER_START_NN` exactly once. Convert physical indexes to printed body pages with `printed_page()`, regenerate the combined Markdown with those numbers, and print the second pass. Assert the second-pass markers resolve to the same physical pages; otherwise fail rather than shipping an inaccurate directory.

- [ ] **Step 3: Overlay headers and page numbers**

Use ReportLab to create one transparent A4 overlay per page and merge it with pypdf. Leave the cover blank; label the two TOC pages `i` and `ii`; number the body from `1`. For body pages, show `Production-grade Agentic Systems` at the outside top edge and `Ch.NN · <chapter title>` at the inside top edge. Use 8pt gray text and a thin rule; never place running matter inside the body box.

- [ ] **Step 4: Add bookmarks and metadata**

With pypdf, set title to `Production-grade Agentic Systems：生产级智能体系统` and language metadata to `zh-CN`. Add one top-level outline entry per chapter pointing to the physical page found by the marker scan. Write atomically to `output/pdf/production-grade-agentic-systems-zh-CN.pdf`.

- [ ] **Step 5: Verify page mapping**

Run: `python workspace/course-pdf/build_pdf.py --build`

Expected: the command reports all 23 chapter starts, confirms stable first/second-pass pagination, and writes the final PDF.

### Task 5: Structural and visual verification

**Files:**
- Create: `workspace/course-pdf/verify_pdf.py`

- [ ] **Step 1: Implement structural checks**

`verify_pdf.py` must fail unless: the file opens; page count exceeds 100; all pages are A4 within one point; extracted text contains all 23 chapter markers/titles; all outline destinations are valid; no page after the cover has fewer than 20 extracted characters unless it is an intentional chapter break; and no replacement glyph `�` appears.

- [ ] **Step 2: Render every page**

Run: `pdftoppm -png -r 120 output/pdf/production-grade-agentic-systems-zh-CN.pdf tmp/pdfs/course-book/pages/page`

Expected: one PNG per PDF page and no Poppler errors.

- [ ] **Step 3: Create contact sheets for visual review**

Use Pillow to create contact sheets containing 12 page thumbnails each. Inspect all sheets, then inspect full-size renders for: cover; both TOC pages; Ch.00 and Ch.22 starts; at least three code-heavy pages; two table-heavy pages; and two Mermaid-heavy pages.

Expected: no clipping, overlap, black squares, malformed diagrams, orphan headings, unreadably small code, or inconsistent chapter transitions.

- [ ] **Step 4: Run final automated verification**

Run: `python workspace/course-pdf/verify_pdf.py output/pdf/production-grade-agentic-systems-zh-CN.pdf`

Expected: `PASS` with page count, 23/23 chapter titles, 23/23 bookmarks, 40/40 Mermaid diagrams, and zero detected replacement glyphs.

- [ ] **Step 5: Remove disposable intermediates**

Delete only `tmp/pdfs/course-book/` after the final PDF and verification report are safely written. Keep the source scripts and final PDF.

