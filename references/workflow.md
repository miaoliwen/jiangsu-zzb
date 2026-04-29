# Workflow

## Authoring Workflow

1. Read the syllabus and assessment scope.
2. Draft the paper structure:
   - section types
   - question counts
   - score distribution
   - difficulty mix
3. Write the exam spec in Markdown-first format unless a structured source already exists.
4. Choose the output variant.
5. Run the build script.
6. Inspect HTML and PDF output.

## Verification Checklist

- Title, subtitle, and confidential label are correct
- Notice block matches the intended exam
- Section counts and scores add up
- Question numbering is correct
- Correct options are highlighted only in `teacher-redline`
- Answers are hidden in `official`
- Formulas render as formatted math, not raw TeX
- Code blocks keep indentation and do not overflow the page
- Page breaks do not create obviously broken sections

## Recommended Build Command

```powershell
.\scripts\build_exam_paper.ps1 `
  -InputPath .\assets\example_exam.md `
  -OutputDir .\build `
  -Variant teacher-redline
```

## Troubleshooting

- **Pandoc not found**: Install Pandoc from https://pandoc.org/installing.html or pass `--pandoc-path` to the script with the full path to the executable.
- **Chrome / Edge headless printing unavailable**: The script falls back to wkhtmltopdf when present. Install wkhtmltopdf from https://wkhtmltopdf.org if neither browser is available.
- **Formulas render as raw TeX in the PDF**: wkhtmltopdf does not support MathML. Use Chrome or Edge headless for correct formula rendering.
- **Chinese characters appear as boxes or are missing in the PDF**: The print environment is missing a CJK font. Install a font such as Noto Sans CJK or Source Han Sans and restart the browser headless process.
- **YAML parse error in frontmatter**: Check for missing quotes around values that contain colons (e.g. `title: "科目代码: 204"`), incorrect indentation, or BOM characters at the start of the file. Save the file as UTF-8 without BOM.
- **`@key` metadata lines not parsed**: Metadata lines must appear immediately after the `##` heading with no blank line between the heading and the first `@` line.
- **Score totals do not add up**: Verify that `score_per_question` × question count equals the value in `description`. The script does not auto-correct this mismatch.
- **Pandoc version incompatibility**: The script requires Pandoc 2.x or later. Run `pandoc --version` to confirm.

