#!/usr/bin/env python3

import argparse
import copy
import concurrent.futures
import html
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import quote


DEFAULT_RENDER_BY_VARIANT = {
    "official": {
        "include_answers": False,
        "include_keywords": False,
        "include_sources": False,
        "include_teacher_notes": False,
        "include_analysis": False,
        "highlight_answer": False,
    },
    "teacher": {
        "include_answers": True,
        "include_keywords": True,
        "include_sources": True,
        "include_teacher_notes": True,
        "include_analysis": True,
        "highlight_answer": False,
    },
    "teacher-redline": {
        "include_answers": True,
        "include_keywords": True,
        "include_sources": True,
        "include_teacher_notes": True,
        "include_analysis": True,
        "highlight_answer": True,
    },
    "review": {
        "include_answers": True,
        "include_keywords": True,
        "include_sources": True,
        "include_teacher_notes": True,
        "include_analysis": True,
        "highlight_answer": False,
    },
}

QUESTION_TYPE_ALIASES = {
    "single_choice": "single_choice",
    "single-choice": "single_choice",
    "single": "single_choice",
    "单选": "single_choice",
    "multiple_choice": "multiple_choice",
    "multiple-choice": "multiple_choice",
    "multiple": "multiple_choice",
    "多选": "multiple_choice",
    "judgement": "judgement",
    "judgment": "judgement",
    "true_false": "judgement",
    "判断": "judgement",
    "fill_blank": "fill_blank",
    "fill-in-the-blank": "fill_blank",
    "blank": "fill_blank",
    "填空": "fill_blank",
    "short_answer": "short_answer",
    "简答": "short_answer",
    "calculation": "calculation",
    "计算": "calculation",
    "proof": "proof",
    "证明": "proof",
    "programming": "programming",
    "coding": "programming",
    "编程": "programming",
    "composite": "composite",
    "综合": "composite",
}

SECTION_CHINESE_NUMERALS = [
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "十一",
    "十二",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--variant",
        choices=["official", "teacher", "teacher-redline", "review"],
    )
    parser.add_argument("--variants")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--pandoc-path")
    parser.add_argument("--chrome-path")
    parser.add_argument("--wkhtmltopdf-path")
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--perf-report", action="store_true")
    return parser.parse_args()


def parse_variants_arg(variants_text: str):
    if not variants_text:
        return []
    variants = [item.strip() for item in variants_text.split(",") if item.strip()]
    invalid = [item for item in variants if item not in DEFAULT_RENDER_BY_VARIANT]
    if invalid:
        raise ValueError(f"Invalid variants: {', '.join(invalid)}")
    seen = set()
    ordered = []
    for item in variants:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def resolve_jobs(value: int) -> int:
    if value is None:
        return 1
    return max(1, int(value))


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dump_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_type(value: str) -> str:
    key = str(value or "").strip().lower().replace(" ", "_")
    return QUESTION_TYPE_ALIASES.get(key, key or "short_answer")


def split_csv_like(text: str):
    items = []
    current = []
    quote_char = None
    depth = 0
    for char in text:
        if quote_char:
            current.append(char)
            if char == quote_char:
                quote_char = None
            continue
        if char in {"'", '"'}:
            quote_char = char
            current.append(char)
            continue
        if char in "[{(":
            depth += 1
        elif char in "]})" and depth > 0:
            depth -= 1
        if char == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        items.append("".join(current).strip())
    return [item for item in items if item]


def parse_scalar(value: str):
    value = value.strip()
    if value == "":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in split_csv_like(inner)]
    if value.startswith("{") and value.endswith("}"):
        return json.loads(value)
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse_simple_yaml(text: str):
    raw_lines = text.splitlines()
    lines = []
    for raw_line in raw_lines:
        if not raw_line.strip():
            lines.append(raw_line.rstrip("\n"))
            continue
        if raw_line.lstrip().startswith("#"):
            continue
        lines.append(raw_line.rstrip("\n"))

    def indentation(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def parse_block(index: int, indent: int):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            return None, index

        current_line = lines[index]
        current_indent = indentation(current_line)
        if current_indent < indent:
            return None, index

        if current_line.strip().startswith("- "):
            result = []
            while index < len(lines):
                line = lines[index]
                if not line.strip():
                    index += 1
                    continue
                line_indent = indentation(line)
                if line_indent < indent or not line.strip().startswith("- "):
                    break
                item_text = line.strip()[2:].strip()
                index += 1
                nested_value = None
                if index < len(lines):
                    next_line = lines[index]
                    if next_line.strip() and indentation(next_line) > line_indent:
                        nested_value, index = parse_block(index, indentation(next_line))
                if item_text == "":
                    result.append(nested_value)
                    continue
                if ":" in item_text and not item_text.startswith(("http://", "https://")):
                    key, value = item_text.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    item = {}
                    if value:
                        item[key] = parse_scalar(value)
                    else:
                        item[key] = nested_value
                        nested_value = None
                    if isinstance(nested_value, dict):
                        item.update(nested_value)
                    result.append(item)
                else:
                    if nested_value is not None:
                        result.append({"value": parse_scalar(item_text), "children": nested_value})
                    else:
                        result.append(parse_scalar(item_text))
            return result, index

        result = {}
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue
            line_indent = indentation(line)
            if line_indent < indent:
                break
            if line_indent > indent:
                raise ValueError(f"Unexpected indentation near: {line}")
            stripped = line.strip()
            if ":" not in stripped:
                raise ValueError(f"Expected key:value pair, got: {line}")
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            index += 1
            if value:
                result[key] = parse_scalar(value)
                continue
            nested = None
            while index < len(lines) and not lines[index].strip():
                index += 1
            if index < len(lines) and indentation(lines[index]) > line_indent:
                nested, index = parse_block(index, indentation(lines[index]))
            result[key] = nested
        return result, index

    parsed, _ = parse_block(0, 0)
    return parsed or {}


def parse_structured_text(text: str):
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    return parse_simple_yaml(text)


def extract_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not match:
        return {}, text
    frontmatter = parse_structured_text(match.group(1))
    body = text[match.end():]
    return frontmatter, body


def parse_metadata_lines(lines):
    metadata = {}
    consumed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("@"):
            break
        consumed += 1
        if ":" not in stripped:
            continue
        key, value = stripped[1:].split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "keywords":
            metadata[key] = [
                item.strip()
                for item in re.split(r"[;,，、]\s*", value)
                if item.strip()
            ]
        else:
            metadata[key] = parse_scalar(value)
    return metadata, consumed


def finalize_section(section):
    normalized = dict(section)
    normalized["type"] = normalize_type(normalized.get("type", "short_answer"))
    normalized["questions"] = ensure_list(normalized.get("questions"))
    return normalized


def parse_question_body(normalized):
    content_lines = normalized.pop("content_lines", [])
    content = "\n".join(content_lines).strip()
    qtype = normalized.get("type") or "short_answer"

    if qtype in {"single_choice", "multiple_choice"}:
        stem_lines = []
        options = []
        current_option = None
        option_pattern = re.compile(r"^([A-H])[\.\閵嗕箽]\s*(.*)$")
        for raw_line in content.splitlines():
            match = option_pattern.match(raw_line.strip())
            if match:
                if current_option is not None:
                    options.append(current_option)
                current_option = {
                    "label": match.group(1),
                    "content": match.group(2).strip(),
                }
                continue
            if current_option is not None:
                current_option["content"] += "\n" + raw_line.strip()
            else:
                stem_lines.append(raw_line)
        if current_option is not None:
            options.append(current_option)
        normalized["stem"] = "\n".join(stem_lines).strip()
        normalized["options"] = options
    else:
        normalized["stem"] = content
        normalized["options"] = ensure_list(normalized.get("options"))
    return normalized


def finalize_composite_child(question):
    normalized = dict(question)
    normalized["type"] = normalize_type(normalized.get("type") or "short_answer")
    normalized["label"] = normalized.get("heading", "").strip()
    normalized = parse_question_body(normalized)
    normalized["keywords"] = ensure_list(normalized.get("keywords"))
    if "answer" in normalized and isinstance(normalized["answer"], str):
        normalized["answer"] = normalized["answer"].strip()
    return normalized


def parse_composite_children(content):
    lines = content.splitlines()
    stem_lines = []
    children = []
    current_child = None
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("### "):
            if current_child is not None:
                children.append(finalize_composite_child(current_child))
            current_child = {
                "heading": stripped[4:].strip(),
                "content_lines": [],
            }
            metadata, consumed = parse_metadata_lines(lines[index + 1:])
            current_child.update(metadata)
            index += consumed + 1
            continue
        if current_child is None:
            stem_lines.append(line)
        else:
            current_child["content_lines"].append(line)
        index += 1

    if current_child is not None:
        children.append(finalize_composite_child(current_child))

    return "\n".join(stem_lines).strip(), children


def finalize_question(question, default_type=None):
    normalized = dict(question)
    resolved_type = normalized.get("type") or default_type or ""
    normalized["type"] = normalize_type(resolved_type)
    content_lines = normalized.pop("content_lines", [])
    content = "\n".join(content_lines).strip()
    qtype = normalized.get("type") or "short_answer"

    heading = normalized.get("heading", "")
    if re.fullmatch(r"\d+", heading):
        normalized["number"] = int(heading)
    else:
        number_match = re.match(r"(\d+)", heading)
        if number_match:
            normalized["number"] = int(number_match.group(1))

    if qtype in {"single_choice", "multiple_choice"}:
        stem_lines = []
        options = []
        current_option = None
        option_pattern = re.compile(r"^([A-H])[\.\銆乚\s*(.*)$")
        for raw_line in content.splitlines():
            match = option_pattern.match(raw_line.strip())
            if match:
                if current_option is not None:
                    options.append(current_option)
                current_option = {
                    "label": match.group(1),
                    "content": match.group(2).strip(),
                }
                continue
            if current_option is not None:
                current_option["content"] += "\n" + raw_line.strip()
            else:
                stem_lines.append(raw_line)
        if current_option is not None:
            options.append(current_option)
        normalized["stem"] = "\n".join(stem_lines).strip()
        normalized["options"] = options
    else:
        normalized["stem"] = content
        normalized["options"] = ensure_list(normalized.get("options"))

    normalized["keywords"] = ensure_list(normalized.get("keywords"))
    if "answer" in normalized and isinstance(normalized["answer"], str):
        normalized["answer"] = normalized["answer"].strip()
    return normalized


def finalize_question_v2(question, default_type=None):
    normalized = dict(question)
    resolved_type = normalized.get("type") or default_type or ""
    normalized["type"] = normalize_type(resolved_type)
    qtype = normalized.get("type") or "short_answer"

    heading = normalized.get("heading", "")
    if re.fullmatch(r"\d+", heading):
        normalized["number"] = int(heading)
    else:
        number_match = re.match(r"(\d+)", heading)
        if number_match:
            normalized["number"] = int(number_match.group(1))

    normalized = parse_question_body(normalized)
    if qtype == "composite":
        stem, children = parse_composite_children(normalized.get("stem", ""))
        normalized["stem"] = stem
        normalized["children"] = children

    normalized["keywords"] = ensure_list(normalized.get("keywords"))
    if "answer" in normalized and isinstance(normalized["answer"], str):
        normalized["answer"] = normalized["answer"].strip()
    return normalized


def parse_markdown_document(text: str):
    frontmatter, body = extract_frontmatter(text)
    sections = []
    current_section = None
    current_question = None

    lines = body.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("# "):
            if current_question is not None:
                current_section["questions"].append(
                    finalize_question_v2(current_question, current_section.get("type"))
                )
                current_question = None
            if current_section is not None:
                sections.append(finalize_section(current_section))
            current_section = {
                "title": stripped[2:].strip(),
                "questions": [],
            }
            metadata, consumed = parse_metadata_lines(lines[index + 1:])
            current_section.update(metadata)
            index += consumed + 1
            continue

        if stripped.startswith("## "):
            if current_section is None:
                current_section = {"title": "未命名题组", "questions": []}
            if current_question is not None:
                current_section["questions"].append(
                    finalize_question_v2(current_question, current_section.get("type"))
                )
            current_question = {
                "heading": stripped[3:].strip(),
                "content_lines": [],
            }
            metadata, consumed = parse_metadata_lines(lines[index + 1:])
            current_question.update(metadata)
            index += consumed + 1
            continue

        if current_question is not None:
            current_question["content_lines"].append(line)
        index += 1

    if current_question is not None and current_section is not None:
        current_section["questions"].append(
            finalize_question_v2(current_question, current_section.get("type"))
        )
    if current_section is not None:
        sections.append(finalize_section(current_section))

    structured_sections = frontmatter.get("sections")
    if structured_sections and not sections:
        sections = structured_sections

    return {
        "exam": frontmatter.get("exam", {}),
        "instructions": ensure_list(frontmatter.get("instructions")),
        "render": frontmatter.get("render", {}),
        "sections": sections,
    }


def load_exam_spec(path: Path):
    text = load_text(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        data = parse_structured_text(text)
    else:
        data = parse_markdown_document(text)
    return normalize_exam_data(data)


def normalize_exam_data(data):
    exam = dict(data.get("exam", {}))
    sections = ensure_list(data.get("sections"))
    render = dict(data.get("render", {}))
    variant = exam.get("variant", "official")
    if variant not in DEFAULT_RENDER_BY_VARIANT:
        variant = "official"
    exam["variant"] = variant

    merged_render = copy.deepcopy(DEFAULT_RENDER_BY_VARIANT[variant])
    merged_render.update(render)
    data["render"] = merged_render

    question_counter = 1
    total_score = 0
    for section in sections:
        section["type"] = normalize_type(section.get("type", "short_answer"))
        questions = ensure_list(section.get("questions"))
        section["questions"] = questions
        for question in questions:
            question["type"] = normalize_type(question.get("type") or section["type"])
            if not question.get("number"):
                question["number"] = question_counter
            question_counter = question["number"] + 1
            question["keywords"] = ensure_list(question.get("keywords"))
            children = ensure_list(question.get("children"))
            question["children"] = children
            if children:
                child_total = 0
                for child in children:
                    child["type"] = normalize_type(child.get("type") or "short_answer")
                    child["keywords"] = ensure_list(child.get("keywords"))
                    child_total += int(child.get("score", 0) or 0)
                total_score += child_total
            else:
                score_value = question.get("score", section.get("score_per_question", 0)) or 0
                total_score += int(score_value)
        if not section.get("description"):
            count = len(questions)
            score_per_question = section.get("score_per_question")
            if score_per_question:
                section_total = count * int(score_per_question)
                section["description"] = f"本大题共 {count} 小题，每小题 {score_per_question} 分，共 {section_total} 分。"
            else:
                section["description"] = ""

    if not exam.get("total_score"):
        exam["total_score"] = total_score
    if not exam.get("title"):
        exam["title"] = "考试试卷"
    if not exam.get("subtitle"):
        exam["subtitle"] = ""
    if not exam.get("confidential_label"):
        exam["confidential_label"] = "机密★启用前"

    data["exam"] = exam
    data["instructions"] = ensure_list(data.get("instructions"))
    data["sections"] = sections
    return data


def find_tool(explicit_path: str, names, fallback_paths):
    if explicit_path:
        path = Path(explicit_path)
        try:
            if path.exists():
                return path
        except OSError:
            pass
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)
    for item in fallback_paths:
        path = Path(item)
        try:
            if path.exists():
                return path
        except OSError:
            continue
    return None


def pandoc_path(explicit=None):
    return find_tool(
        explicit,
        ["pandoc"],
        [
            r"C:\Program Files\Pandoc\pandoc.exe",
            r"C:\Program Files (x86)\Pandoc\pandoc.exe",
            r"C:\Users\ROG\AppData\Local\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-3.9.0.2\pandoc.exe",
        ],
    )


def chrome_like_path(explicit=None):
    return find_tool(
        explicit,
        ["chrome", "msedge"],
        [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ],
    )


def wkhtmltopdf_path(explicit=None):
    return find_tool(
        explicit,
        ["wkhtmltopdf"],
        [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        ],
    )


def fallback_markdown_to_html(source: str, inline: bool = False):
    text = source.strip()
    if not text:
        return ""
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    if inline:
        return escaped.replace("\n", "<br />")
    return "".join(f"<p>{line}</p>" for line in escaped.splitlines() if line.strip())


def render_fragment(markdown_text: str, pandoc_exe: Path, inline=False):
    source = markdown_text.strip()
    if not source:
        return ""
    if not pandoc_exe:
        return fallback_markdown_to_html(source, inline=inline)
    command = [
        str(pandoc_exe),
        "--from=markdown+tex_math_dollars+fenced_code_blocks+pipe_tables",
        "--to=html5",
        "--mathml",
    ]
    completed = subprocess.run(
        command,
        input=source,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Pandoc fragment conversion failed")
    output = completed.stdout.strip()
    if inline:
        paragraph_match = re.fullmatch(r"<p>(.*)</p>", output, re.DOTALL)
        if paragraph_match:
            return paragraph_match.group(1).strip()
    return output


def answer_set(answer):
    if answer is None:
        return set()
    if isinstance(answer, list):
        return {str(item).strip().upper() for item in answer if str(item).strip()}
    answer_text = str(answer).replace(",", "").replace(" ", "").upper()
    if not answer_text:
        return set()
    if len(answer_text) > 1 and answer_text.isalpha():
        return set(answer_text)
    return {answer_text}


def option_grid_class(options):
    longest = max((len(re.sub(r"\s+", "", option.get("content", ""))) for option in options), default=0)
    return "options-grid single-column" if longest > 22 else "options-grid"


def replace_blank_lines(text: str):
    return re.sub(r"_{4,}", lambda m: f'<span class="fill-blank-line">{"_" * len(m.group(0))}</span>', text)


def append_question_extras(parts, item, render, pandoc_exe, indent="  "):
    if render.get("include_answers") and item.get("answer") not in {None, ""}:
        parts.append(
            f'{indent}<div class="answer-block"><span class="block-label">答案:</span>'
            + html.escape(str(item.get("answer")))
            + "</div>"
        )
    if render.get("include_keywords") and item.get("keywords"):
        parts.append(
            f'{indent}<div class="keywords-block"><span class="block-label">解题关键词:</span>'
            + html.escape("、".join(str(keyword) for keyword in item.get("keywords")))
            + "</div>"
        )
    if render.get("include_sources") and item.get("source"):
        source_html = render_fragment(str(item.get("source")), pandoc_exe, inline=True)
        parts.append(
            f'{indent}<div class="source-block"><span class="block-label">题源:</span>'
            + source_html
            + "</div>"
        )
    if render.get("include_teacher_notes") and item.get("teacher_note"):
        note_html = render_fragment(str(item.get("teacher_note")), pandoc_exe)
        parts.append(
            f'{indent}<div class="teacher-note-block"><span class="block-label">教师备注:</span>'
            + note_html
            + "</div>"
        )
    if render.get("include_analysis") and item.get("analysis"):
        analysis_html = render_fragment(str(item.get("analysis")), pandoc_exe)
        parts.append(
            f'{indent}<div class="analysis-block"><span class="block-label">解析:</span>'
            + analysis_html
            + "</div>"
        )

    lines = int(item.get("answer_lines") or 0)
    for _ in range(lines):
        parts.append(f"{indent}<div class=\"source-block\">________________________________________</div>")


def render_composite_children(children, render, pandoc_exe):
    parts = ['  <div class="composite-children">']
    for child in children:
        child_stem = render_fragment(replace_blank_lines(child.get("stem", "")), pandoc_exe)
        parts.extend(
            [
                '    <div class="composite-child">',
                f'      <div class="composite-child-heading">{html.escape(str(child.get("label", "")))}</div>',
                f'      <div class="composite-child-body">{child_stem}</div>',
            ]
        )
        append_question_extras(parts, child, render, pandoc_exe, indent="      ")
        parts.append("    </div>")
    parts.append("  </div>")
    return parts


def render_question(question, render, pandoc_exe):
    qtype = question.get("type", "short_answer")
    stem_markdown = replace_blank_lines(question.get("stem", ""))
    stem_html = render_fragment(stem_markdown, pandoc_exe)
    parts = [
        '<article class="exam-question">',
        '  <div class="question-head">',
        f'    <div class="question-number">{question["number"]}.</div>',
        f'    <div class="question-body">{stem_html}</div>',
        "  </div>",
    ]

    if qtype in {"single_choice", "multiple_choice"}:
        options = ensure_list(question.get("options"))
        grid_class = option_grid_class(options)
        parts.append(f'  <div class="{grid_class}">')
        correct = answer_set(question.get("answer"))
        for option in options:
            label = option.get("label", "")
            content_html = render_fragment(option.get("content", ""), pandoc_exe)
            classes = ["option-item"]
            if render.get("highlight_answer") and label.upper() in correct:
                classes.append("correct-answer")
            parts.append(f'    <div class="{" ".join(classes)}">')
            parts.append(f'      <div class="option-label">{html.escape(label)}.</div>')
            parts.append(f'      <div class="option-content">{content_html}</div>')
            parts.append("    </div>")
        parts.append("  </div>")

    if render.get("include_answers") and question.get("answer") not in {None, ""}:
        parts.append(
            '  <div class="answer-block"><span class="block-label">答案:</span>'
            + html.escape(str(question.get("answer")))
            + "</div>"
        )
    if render.get("include_keywords") and question.get("keywords"):
        parts.append(
            '  <div class="keywords-block"><span class="block-label">解题关键词:</span>'
            + html.escape("、".join(str(item) for item in question.get("keywords")))
            + "</div>"
        )
    if render.get("include_sources") and question.get("source"):
        source_html = render_fragment(str(question.get("source")), pandoc_exe, inline=True)
        parts.append(
            '  <div class="source-block"><span class="block-label">题源:</span>'
            + source_html
            + "</div>"
        )
    if render.get("include_teacher_notes") and question.get("teacher_note"):
        note_html = render_fragment(str(question.get("teacher_note")), pandoc_exe)
        parts.append(
            '  <div class="teacher-note-block"><span class="block-label">教师备注:</span>'
            + note_html
            + "</div>"
        )
    if render.get("include_analysis") and question.get("analysis"):
        analysis_html = render_fragment(str(question.get("analysis")), pandoc_exe)
        parts.append(
            '  <div class="analysis-block"><span class="block-label">解析:</span>'
            + analysis_html
            + "</div>"
        )

    if qtype in {"short_answer", "calculation", "proof", "programming", "composite"}:
        lines = int(question.get("answer_lines") or 0)
        for _ in range(lines):
            parts.append('  <div class="source-block">________________________________________</div>')

    parts.append("</article>")
    return "\n".join(parts)


def render_question_v2(question, render, pandoc_exe):
    qtype = question.get("type", "short_answer")
    stem_markdown = replace_blank_lines(question.get("stem", ""))
    stem_html = render_fragment(stem_markdown, pandoc_exe)
    parts = [
        '<article class="exam-question">',
        '  <div class="question-head">',
        f'    <div class="question-number">{question["number"]}.</div>',
        f'    <div class="question-body">{stem_html}</div>',
        "  </div>",
    ]

    if qtype in {"single_choice", "multiple_choice"}:
        options = ensure_list(question.get("options"))
        grid_class = option_grid_class(options)
        parts.append(f'  <div class="{grid_class}">')
        correct = answer_set(question.get("answer"))
        for option in options:
            label = option.get("label", "")
            content_html = render_fragment(option.get("content", ""), pandoc_exe)
            classes = ["option-item"]
            if render.get("highlight_answer") and label.upper() in correct:
                classes.append("correct-answer")
            parts.append(f'    <div class="{" ".join(classes)}">')
            parts.append(f'      <div class="option-label">{html.escape(label)}.</div>')
            parts.append(f'      <div class="option-content">{content_html}</div>')
            parts.append("    </div>")
        parts.append("  </div>")

    if qtype == "composite":
        parts.extend(render_composite_children(question.get("children", []), render, pandoc_exe))

    append_question_extras(parts, question, render, pandoc_exe)

    parts.append("</article>")
    return "\n".join(parts)


def render_html_document(data, pandoc_exe: Path):
    css_text = load_text(skill_root() / "assets" / "jiangsu_exam.css")
    exam = data["exam"]
    render = data["render"]
    variant = exam["variant"]
    wrapper_classes = f'paper variant-{variant} {"teacher-redline" if render.get("highlight_answer") else ""}'

    instruction_items = "".join(
        f"<li>{render_fragment(item, pandoc_exe, inline=True)}</li>" for item in data.get("instructions", [])
    )

    sections_html = []
    for section_index, section in enumerate(data.get("sections", []), start=1):
        numeral = SECTION_CHINESE_NUMERALS[section_index - 1] if section_index <= len(SECTION_CHINESE_NUMERALS) else str(section_index)
        question_html = "\n".join(
            render_question_v2(question, render, pandoc_exe)
            for question in section.get("questions", [])
        )
        sections_html.append(
            "\n".join(
                [
                    '<section class="exam-section">',
                    '  <div class="section-heading">',
                    f'    <span>{numeral}、{html.escape(section.get("title", ""))}</span>',
                    (
                        f'    <span class="section-description">{html.escape(section.get("description", ""))}</span>'
                        if section.get("description")
                        else ""
                    ),
                    "  </div>",
                    question_html,
                    "</section>",
                ]
            )
        )

    subtitle_html = f'<div class="subtitle">{html.escape(str(exam.get("subtitle", "")))}</div>' if exam.get("subtitle") else ""
    notice_block = ""
    if instruction_items:
        notice_block = (
            '<div class="notice-block"><div class="notice-title">娉ㄦ剰浜嬮」:</div><ol>'
            + instruction_items
            + "</ol></div>"
        )

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '  <meta charset="utf-8" />',
            '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
            f"  <title>{html.escape(str(exam.get('title', '鑰冭瘯璇曞嵎')))}</title>",
            "  <style>",
            css_text,
            "  </style>",
            "</head>",
            "<body>",
            f'  <div class="{wrapper_classes.strip()}">',
            f'    <div class="confidential-label">{html.escape(str(exam.get("confidential_label", "")))}</div>',
            '    <div class="title-block">',
            f'      <h1>{html.escape(str(exam.get("title", "")))}</h1>',
            subtitle_html,
            "    </div>",
            notice_block,
            "\n".join(sections_html),
            "  </div>",
            "</body>",
            "</html>",
        ]
    )


def path_to_file_uri(path: Path):
    return "file:///" + quote(str(path).replace("\\", "/"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_cache_key(input_text: str, variant: str, input_path: Path) -> str:
    payload = {
        "input_sha256": sha256_text(input_text),
        "variant": variant,
        "script": "build_exam_paper.py",
        "script_mtime_ns": Path(__file__).stat().st_mtime_ns,
        "input": str(input_path),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256_text(serialized)


def load_cache_manifest(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(load_text(path))
    except Exception:
        return {}


def save_cache_manifest(path: Path, data):
    dump_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def write_perf_report(path: Path, report):
    dump_text(path, json.dumps(report, ensure_ascii=False, indent=2))


def output_stem_name(input_path: Path, data):
    title = str(data.get("exam", {}).get("title", "")).strip()
    if not title:
        return input_path.stem
    sanitized = re.sub(r'[<>:"/\\|?*]+', "-", title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip().rstrip(".")
    return sanitized or input_path.stem


def print_html_to_pdf(html_path: Path, pdf_path: Path, chrome_exe: Path = None, wkhtmltopdf_exe: Path = None):
    if chrome_exe:
        command = [
            str(chrome_exe),
            "--headless=new",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--enable-local-file-accesses",
            "--no-pdf-header-footer",
            "--virtual-time-budget=5000",
            f"--print-to-pdf={pdf_path}",
            path_to_file_uri(html_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False, encoding="utf-8")
        if completed.returncode == 0 and pdf_path.exists():
            return
    if wkhtmltopdf_exe:
        command = [
            str(wkhtmltopdf_exe),
            "--enable-local-file-access",
            str(html_path),
            str(pdf_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False, encoding="utf-8")
        if completed.returncode == 0 and pdf_path.exists():
            return
    raise RuntimeError("Unable to export PDF. Chrome/Edge headless and wkhtmltopdf both failed or were unavailable.")


def export_pdf_job(html_path: Path, pdf_path: Path, chrome_exe: Path = None, wkhtmltopdf_exe: Path = None):
    start = time.perf_counter()
    print_html_to_pdf(html_path, pdf_path, chrome_exe, wkhtmltopdf_exe)
    return pdf_path, (time.perf_counter() - start)


def main():
    args = parse_args()
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.fast:
        args.html_only = True

    if args.variant and args.variants:
        raise ValueError("--variant and --variants cannot be used together")

    variants = parse_variants_arg(args.variants)
    jobs = resolve_jobs(args.jobs)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_path.parent / "build"
    output_dir.mkdir(parents=True, exist_ok=True)

    perf = {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "timings_ms": {},
        "cache": {
            "enabled": not args.no_cache,
            "hit": False,
            "key": None,
        },
    }

    t0 = time.perf_counter()
    input_text = load_text(input_path)
    perf["timings_ms"]["read_input"] = round((time.perf_counter() - t0) * 1000, 2)

    variant_for_key = args.variant if args.variant else (",".join(variants) if variants else "from-input")
    cache_key = build_cache_key(input_text, variant_for_key, input_path)
    perf["cache"]["key"] = cache_key

    stem_fallback = input_path.stem
    cache_manifest_path = output_dir / ".build_cache.json"

    if not args.no_cache:
        cache_manifest = load_cache_manifest(cache_manifest_path)
        entry = cache_manifest.get(cache_key, {})
        can_hit = (
            entry.get("json_path")
            and entry.get("html_path")
            and Path(entry["json_path"]).exists()
            and Path(entry["html_path"]).exists()
            and (args.html_only or args.json_only or (entry.get("pdf_path") and Path(entry["pdf_path"]).exists()))
        )
        if can_hit:
            perf["cache"]["hit"] = True
            if args.json_only:
                print(entry["json_path"])
            elif args.html_only:
                print(entry["html_path"])
            else:
                print(entry["json_path"])
                print(entry["html_path"])
                print(entry["pdf_path"])
            if args.perf_report:
                perf["timings_ms"]["total"] = round((time.perf_counter() - t0) * 1000, 2)
                write_perf_report(output_dir / f"{stem_fallback}.perf-report.json", perf)
            return

    t1 = time.perf_counter()
    data = load_exam_spec(input_path)
    perf["timings_ms"]["parse_and_normalize"] = round((time.perf_counter() - t1) * 1000, 2)

    selected_variants = []
    if args.variant:
        selected_variants = [args.variant]
    elif variants:
        selected_variants = variants
    else:
        selected_variants = [data["exam"].get("variant", "official")]

    t2 = time.perf_counter()
    pandoc_exe = pandoc_path(args.pandoc_path)
    perf["timings_ms"]["resolve_pandoc"] = round((time.perf_counter() - t2) * 1000, 2)
    needs_pandoc = not args.fast and not args.html_only and not args.json_only
    if not pandoc_exe and needs_pandoc:
        raise RuntimeError("Pandoc was not found. Install pandoc or pass --pandoc-path.")

    stem_name = output_stem_name(input_path, data)
    json_path = output_dir / f"{stem_name}.normalized.json"

    t3 = time.perf_counter()
    dump_text(json_path, json.dumps(data, ensure_ascii=False, indent=2))
    perf["timings_ms"]["write_json"] = round((time.perf_counter() - t3) * 1000, 2)
    if args.json_only:
        print(json_path)
        if args.perf_report:
            perf["timings_ms"]["total"] = round((time.perf_counter() - t0) * 1000, 2)
            write_perf_report(output_dir / f"{stem_name}.perf-report.json", perf)
        return

    html_paths = []
    pdf_tasks = []
    pdf_paths = []

    render_html_total = 0.0
    render_pdf_total = 0.0
    chrome_exe = None
    wkhtml_exe = None

    for variant in selected_variants:
        variant_data = copy.deepcopy(data)
        variant_data["exam"]["variant"] = variant
        variant_data["render"] = copy.deepcopy(DEFAULT_RENDER_BY_VARIANT[variant])
        html_path = output_dir / f"{stem_name}.{variant}.html"
        pdf_path = output_dir / f"{stem_name}.{variant}.pdf"

        ts_html = time.perf_counter()
        html_content = render_html_document(variant_data, pandoc_exe)
        dump_text(html_path, html_content)
        render_html_total += time.perf_counter() - ts_html
        html_paths.append(html_path)

        if not args.html_only:
            pdf_tasks.append((html_path, pdf_path))

    perf["timings_ms"]["render_html"] = round(render_html_total * 1000, 2)
    if not args.html_only:
        if chrome_exe is None and wkhtml_exe is None:
            chrome_exe = chrome_like_path(args.chrome_path)
            wkhtml_exe = wkhtmltopdf_path(args.wkhtmltopdf_path)

        if jobs <= 1 or len(pdf_tasks) <= 1:
            for html_path, pdf_path in pdf_tasks:
                exported_pdf_path, elapsed = export_pdf_job(html_path, pdf_path, chrome_exe, wkhtml_exe)
                render_pdf_total += elapsed
                pdf_paths.append(exported_pdf_path)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = [
                    executor.submit(export_pdf_job, html_path, pdf_path, chrome_exe, wkhtml_exe)
                    for html_path, pdf_path in pdf_tasks
                ]
                for future in concurrent.futures.as_completed(futures):
                    exported_pdf_path, elapsed = future.result()
                    render_pdf_total += elapsed
                    pdf_paths.append(exported_pdf_path)

            pdf_paths.sort(key=lambda p: str(p))

        perf["timings_ms"]["render_pdf"] = round(render_pdf_total * 1000, 2)

    if not args.no_cache:
        cache_manifest = load_cache_manifest(cache_manifest_path)
        cache_manifest[cache_key] = {
            "json_path": str(json_path),
            "html_path": str(html_paths[0]) if html_paths else None,
            "pdf_path": str(pdf_paths[0]) if pdf_paths else None,
        }
        save_cache_manifest(cache_manifest_path, cache_manifest)

    perf["timings_ms"]["total"] = round((time.perf_counter() - t0) * 1000, 2)
    if args.perf_report:
        write_perf_report(output_dir / f"{stem_name}.perf-report.json", perf)

    print(json_path)
    for item in html_paths:
        print(item)
    for item in pdf_paths:
        print(item)


if __name__ == "__main__":
    main()
