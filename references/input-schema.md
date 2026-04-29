# Input Schema

## Canonical Model

The normalized exam object has this shape:

```json
{
  "exam": {
    "title": "江苏省2024年普通高校“专转本”选拔考试 计算机专业大类专业综合基础理论 试卷",
    "subtitle": "科目代码: 204",
    "confidential_label": "机密★启用前",
    "duration_minutes": 120,
    "total_score": 150,
    "variant": "official",
    "theme": "jiangsu-zhuanzhuanben-computer"
  },
  "instructions": [
    "本卷分为试卷和答题卡两部分，考生必须在答题卡上作答，作答在试卷上无效。"
  ],
  "render": {
    "include_answers": false,
    "include_keywords": false,
    "include_sources": false,
    "include_teacher_notes": false,
    "highlight_answer": false
  },
  "sections": [
    {
      "title": "单项选择题",
      "type": "single_choice",
      "score_per_question": 2,
      "description": "本大题共 50 小题，每小题 2 分，共 100 分。在每小题列出的选项中只有一项最符合题目要求的。",
      "questions": []
    }
  ]
}
```

## Supported Question Types

- `single_choice`
- `multiple_choice`
- `judgement`
- `fill_blank`
- `short_answer`
- `calculation`
- `proof`
- `programming`
- `composite`

## Markdown-First Format

Start with frontmatter:

```yaml
---
exam:
  title: 江苏省普通高校“专转本”选拔考试 计算机专业大类专业综合基础理论 试卷
  subtitle: 科目代码: 204
  confidential_label: 机密★启用前
  duration_minutes: 120
  total_score: 150
  variant: official
render:
  include_answers: false
instructions:
  - 本卷分为试卷和答题卡两部分，考生必须在答题卡上作答，作答在试卷上无效。
  - 作答前务必将姓名和准考证号填写在指定位置。
---
```

Then write sections and questions:

```markdown
# 单项选择题
@type: single_choice
@score_per_question: 2
@description: 本大题共 2 小题，每小题 2 分，共 4 分。在每小题列出的选项中只有一项最符合题目要求的。

## 1
@answer: C
@keywords: 内存储器
@source: 《计算机应用基础强化习题集》P11
@teacher_note: 【典型习题·单选】根据存储器芯片的功能及物理特性，目前用作PC机主存储器的是（ ）
以下属于内存储器的是（ ）

A. 移动硬盘
B. U 盘
C. SRAM
D. SD 卡
```

## Question Metadata Keys

Use `@key: value` lines immediately under the `##` heading.

- `@type` — override the section question type for this question only
- `@answer` — correct answer; string for single-choice/judgement, comma-separated or array for multiple-choice
- `@keywords` — comma-separated or semicolon-separated topic tags; shown in `teacher` and `review` variants
- `@source` — textbook/page reference; shown in `teacher` and `review` variants
- `@teacher_note` — instructor annotation shown before the stem in `teacher` and `review` variants
- `@analysis` — solution explanation or marking guide; shown in `teacher`, `teacher-redline`, and `review` variants
- `@score` — per-question score override; takes precedence over the section-level `score_per_question`
- `@answer_lines` — number of blank answer lines to reserve below the stem (used for `programming` and `short_answer` questions)

`@keywords` accepts comma-separated or semicolon-separated values.

## Structured JSON/YAML Notes

- Prefer explicit arrays and objects.
- Avoid anchors, aliases, and advanced YAML tags.
- Option objects may be either strings or `{ "label": "A", "content": "..." }`.
- Multi-part composite questions may use a `children` array.

## Composite Question Format

A `composite` question groups sub-questions under a shared stem. Write it in Markdown-first format as:

```markdown
# 综合题
@type: composite
@score_per_question: 0
@description: 本大题共 1 小题，共 15 分。根据题目要求作答。

## 7
阅读以下程序片段，回答下列问题。

```python
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
```

### 7.1
@answer: 递归
@score: 5
该函数使用了什么算法思路？（5分）

### 7.2
@answer: 指数级，O(2^n)
@score: 5
该算法的时间复杂度是多少？（5分）

### 7.3
@answer_lines: 6
@score: 5
请改写为迭代版本。（5分）
```

Rules for composite questions:
- The parent `##` heading holds the shared stem and any shared context.
- Sub-questions use `###` headings.
- Each sub-question may have its own `@answer`, `@score`, `@answer_lines`, and `@analysis`.
- The parent `@score_per_question` is typically `0`; scores live on sub-questions.

## Objective Question Rules

For `single_choice` and `multiple_choice`, store options as:

```json
"options": [
  { "label": "A", "content": "..." },
  { "label": "B", "content": "..." }
]
```

Answers may be:

- `"C"`
- `"ABD"`
- `["A", "B", "D"]`

## Render Flags

These flags may appear under `render` or may be inferred from `variant`:

- `include_answers`
- `include_keywords`
- `include_sources`
- `include_teacher_notes`
- `include_analysis`
- `highlight_answer`

Allowed `variant` values: `official`, `teacher`, `teacher-redline`, `review`.
