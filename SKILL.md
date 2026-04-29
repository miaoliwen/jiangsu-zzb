---
name: jiangsu-exam-paper-pdf-generator
description: Generate Jiangsu专转本-style computer exam papers from syllabus, assessment scope, and question plans, then export polished PDFs with strict exam-paper layout. Use when Claude needs to (1) turn Markdown-first or structured JSON/YAML exam specs into formal试卷, (2) generate official, teacher, or review variants of the same paper, (3) preserve formulas, code blocks, and print layout in PDF, or (4) render江苏专转本计算机考试风格的试卷与解析稿。
---

# Jiangsu Exam Paper PDF Generator

## Prerequisites

- **Python**: 3.8 or higher
- **Pandoc**: 2.x or later (install from https://pandoc.org/installing.html)
- **PDF Engine** (one of the following):
  - Google Chrome or Microsoft Edge (recommended, for proper formula rendering)
  - wkhtmltopdf (fallback, formulas may render as raw TeX)

## Quick Start

```powershell
# 1. Create an exam spec (see assets/example_exam.md for format)

# 2. Build the PDF
.\scripts\build_exam_paper.ps1 `
  -InputPath .\assets\example_exam.md `
  -OutputDir .\build `
  -Variant teacher-redline

# 3. Check .\build\ directory for the generated PDF
```

## Overview

Use this skill when the user wants a reusable workflow that turns an exam outline, test scope, and authored question plans into a formal Jiangsu专转本-style computer exam paper. The bundled scripts focus on deterministic rendering and PDF export. Claude is responsible for reading the syllabus, drafting the actual questions, and filling the schema.

## Agent Guidance

When using this skill, prefer the following operating pattern:

1. Extract the exam structure first:
   - section types
   - question counts
   - score distribution
   - difficulty mix
2. Unless the user explicitly asks for a practice set, introductory worksheet, or easy mock, default the difficulty to a formal Jiangsu专转本 examination level.
   - Prefer medium-to-high discrimination questions over definition-only recall
   - Use plausible distractors for objective questions; avoid giveaway wrong options
   - Include cross-topic reasoning, code reading, algorithmic thinking, and operational judgment where the syllabus supports it
   - Keep the paper solvable within the official time limit, but do not flatten it into a basic drill sheet
3. If the user only provides a syllabus or assessment scope, draft a complete exam spec before building.
   - Match the structure and pressure level of a real selection exam, not a classroom quiz
   - Reserve a smaller share for direct recall questions and a larger share for applied and discriminating items
4. Prefer Markdown-first input unless another tool already produced stable structured JSON or YAML.
5. Choose the output variant from the user intent:
   - formal student-facing paper -> `official`
   - teacher copy with answers and notes -> `teacher`
   - teacher copy with red-highlighted correct options -> `teacher-redline`
   - review copy with the fullest visible metadata -> `review`
6. Before exporting PDF, verify that section counts, score totals, difficulty mix, and visible answer layers match the requested variant.

## Workflow

1. Read the user-provided syllabus, assessment scope, and any sample paper constraints.
   - If the user does not specify difficulty, assume the target is a real formal exam rather than a practice handout.
2. Choose the input mode:
   - Markdown-first: preferred for hand-authored exam specs.
   - Structured JSON/YAML: preferred when another tool already produced canonical data.
3. Build or edit the exam spec so it matches the schema in [references/input-schema.md](references/input-schema.md).
   - Tune the question set so the overall paper has real screening power: not only memory checks, but also application, comparison, debugging, tracing, and synthesis.
4. Confirm the desired output variant:
   - `official`: formal exam paper only
   - `teacher`: answers, keywords, sources, and notes visible
   - `teacher-redline`: same as `teacher`, plus correct options highlighted in red
   - `review`: full review metadata visible

   If `--variant` is not passed on the command line, the script uses the `variant` field in the exam frontmatter. If that field is also absent, it defaults to `official`.
5. Run `scripts/build_exam_paper.py` to normalize the spec, render HTML, and export PDF.
6. Verify the generated PDF. Pay special attention to:
   - title block and notice block
   - section descriptions and numbering
   - whether the final paper reads like a formal exam instead of a low-difficulty exercise sheet
   - page breaks
   - formulas
   - code indentation and line wrapping

## Difficulty Baseline

By default, authored papers should target the difficulty and discrimination level of a real Jiangsu专转本 selection exam.

- Use authentic exam tone, not tutorial tone
- Avoid padding the paper with too many obvious one-step questions
- For single-choice and multiple-choice items, make distractors technically credible
- For programming and composite items, prefer code reading, debugging, tracing, and applied design over rote template reproduction
- Let harder questions come from reasoning depth and concept integration, not from ambiguous wording
- If the user asks for a practice set, intensive drill, or foundation review, that request overrides this default baseline

## Markdown-First Input

Prefer Markdown when the user is iterating with you.

The expected structure is:

1. YAML-like frontmatter for exam metadata and render options.
2. `#` headings for sections.
3. `@key: value` lines under each section or question for metadata.
4. `##` headings for questions.

Read [references/input-schema.md](references/input-schema.md) before authoring or editing the source file. The bundled sample file `assets/example_exam.md` shows the exact pattern.

Minimal example:

```markdown
---
exam:
  title: 江苏省普通高校“专转本”选拔考试 计算机专业大类专业综合基础理论 试卷
  subtitle: 科目代码: 204
  duration_minutes: 120
  total_score: 2
  variant: official
instructions:
  - 本卷分为试卷和答题卡两部分，作答在试卷上无效。
---

# 单项选择题
@type: single_choice
@score_per_question: 2
@description: 本大题共 1 小题，每小题 2 分，共 2 分。

## 1
@answer: C
以下属于内存储器的是（ ）

A. 移动硬盘
B. U 盘
C. SRAM
D. SD 卡
```

## Structured Input

JSON and YAML files may define the full canonical structure directly. Use this mode when the exam plan already exists as structured data or when another process produced question objects automatically.

Keep the schema close to the reference file. Avoid advanced YAML features such as anchors, aliases, and custom tags. The bundled parser intentionally supports only a practical subset.

## Variant Rules

- `official`:
  - hide answers
  - hide keywords
  - hide source notes
  - hide teacher notes
  - never use red highlight
- `teacher`:
  - show answers
  - show keywords
  - show source notes
  - show teacher notes
  - show `@analysis` blocks
  - no red highlight unless the user explicitly asks
- `teacher-redline`:
  - same as `teacher`
  - render correct options in red for objective questions
- `review`:
  - show answers
  - show keywords
  - show source notes
  - show teacher notes
  - show `@analysis` blocks
  - no red highlight

The user explicitly said that red annotations and answer blocks are later-added layers, not part of the formal paper body. Treat that as a hard layout rule.

## Rendering Rules

- Use the Jiangsu专转本 style notes in [references/layout-rules.md](references/layout-rules.md).
- Keep A4 portrait layout.
- Use a centered title block.
- Use light-blue question stems and black body text for the default theme.
- Preserve `____` blank lines in fill-in-the-blank questions.
- For programming questions, keep monospace code blocks and indentation.
- For formulas, rely on the Pandoc-to-HTML conversion with MathML output, then print from Chrome or Edge when available.

## Scripts

### `scripts/build_exam_paper.py`

Primary entry point. It:

1. loads Markdown, JSON, or YAML exam specs
2. normalizes them into canonical JSON
3. renders HTML with the bundled stylesheet
4. exports PDF through headless Chrome, Edge, or wkhtmltopdf

Typical command (use the PowerShell wrapper so you do not need to locate the Python executable):

```powershell
.\scripts\build_exam_paper.ps1 `
  -InputPath .\assets\example_exam.md `
  -OutputDir .\build `
  -Variant teacher-redline
```

If you must call the Python script directly:

```powershell
# Example with explicit Python path
& "C:\Users\<username>\AppData\Local\Programs\Python\Python311\python.exe" `
  scripts/build_exam_paper.py `
  --input assets/example_exam.md `
  --output-dir build `
  --variant teacher-redline

# Or if python is in PATH
python scripts/build_exam_paper.py --input assets/example_exam.md --output-dir build
```

Optional flags:
- `--pandoc-path` — explicit path to Pandoc executable
- `--chrome-path` — explicit path to Chrome/Edge for PDF export
- `--wkhtmltopdf-path` — explicit path to wkhtmltopdf fallback
- `--html-only` — stop after HTML generation
- `--json-only` — stop after normalized JSON generation

These flags apply to direct invocation of `scripts/build_exam_paper.py`. The PowerShell wrapper does not currently expose them.

### `scripts/build_exam_paper.ps1`

Windows convenience wrapper around the Python script. Use it when the environment already has PowerShell but not a preselected Python executable.

Current wrapper behavior:

- accepts `-InputPath`, `-OutputDir`, `-Variant`, and `-PythonPath`
- does not currently expose `--pandoc-path`, `--chrome-path`, `--wkhtmltopdf-path`, `--html-only`, or `--json-only`
- uses a machine-specific default `PythonPath`, so it may need an explicit override on another Windows environment

If the wrapper fails because the default Python path is unavailable, either pass `-PythonPath` explicitly or call `python scripts/build_exam_paper.py ...` directly.

## Assets

- `assets/jiangsu_exam.css`: print stylesheet for the Jiangsu专转本 computer exam style
- `assets/example_exam.md`: minimal Markdown-first source file demonstrating all supported question types

## Cases

Full-length real exam papers live in `cases/`. Use them as the primary authoring reference when generating a complete paper:

- `cases/zhuanzhuanben-computer-foundation-paper.md`: a complete 专转本 computer exam paper
- `cases/zhuanzhuanben-computer-foundation-intensive.md`: an intensive practice set for the same exam

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Pandoc not found** | Install from https://pandoc.org/installing.html or pass `--pandoc-path` |
| **Browser/Chrome not found** | Install Chrome/Edge, or install wkhtmltopdf as fallback |
| **Formulas render as raw TeX** | Use Chrome/Edge instead of wkhtmltopdf |
| **Chinese characters as boxes** | Install Noto Sans CJK or Source Han Sans font |
| **YAML parse error** | Check quotes around colons, indentation, save as UTF-8 without BOM |
| **Metadata `@key` not parsed** | Ensure no blank line between `##` heading and first `@` line |
| **Score totals mismatch** | Verify `score_per_question` × count equals section description |
| **Need `--html-only` or custom executable paths while using `.ps1`** | Call `scripts/build_exam_paper.py` directly because the wrapper does not expose all Python flags |

See [references/workflow.md](references/workflow.md) for full troubleshooting details.

## References

- [references/input-schema.md](references/input-schema.md): schema, field meanings, and Markdown conventions
- [references/layout-rules.md](references/layout-rules.md): visual and print layout rules extracted from the provided sample papers
- [references/workflow.md](references/workflow.md): operational workflow and verification checklist
