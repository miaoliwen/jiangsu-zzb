# 江苏专转本计算机试卷 PDF 生成器

## 项目简介

这是一个面向 **江苏专转本计算机类考试** 的试卷生成与排版项目。

项目可以将 Markdown、JSON、YAML 等形式编写的试卷草稿，转换为统一的规范化数据，并进一步渲染为适合打印与交付的 HTML / PDF 成品。它适用于以下场景：

- 根据考试大纲、考查范围和题目规划生成正式试卷
- 为同一套题目生成学生版、教师版、红批版等不同输出版本
- 保留公式、代码块、分页与版式要求，输出可直接检查与交付的 PDF
- 为 AI Agent 或人工协作提供一套可复用的出卷 workflow

## 项目成果

本项目目前已经完成了以下成果：

- 实现了 **Markdown / JSON / YAML -> HTML / PDF** 的自动化试卷生成链路
- 实现了同一套试题内容的多版本输出：
  - `official`
  - `teacher`
  - `teacher-redline`
  - `review`
- 建立了统一的试卷规范化数据结构，可输出 `normalized.json`
- 支持专转本计算机试卷常见题型的结构化建模与排版输出
- 已生成完整样例产物，并已交付多套真实试卷的 HTML / PDF 文件
- 已整理出可供 AI Agent 复用的 skill、schema 与 workflow 文档

## 核心特性

### 1. 多种输入方式

项目支持两类输入模式：

- **Markdown-first**
  - 适合人工编写、与 AI 协作迭代试卷内容
- **Structured JSON / YAML**
  - 适合其他流程已经产出结构化题目数据时直接接入

### 2. 统一规范化输出

无论原始输入是 Markdown、JSON 还是 YAML，都会先转换为统一的规范化 JSON，便于：

- 检查数据结构是否正确
- 追踪最终渲染使用的数据
- 在后续流程中复用试卷内容

### 3. 多版本试卷输出

同一份题目数据可以根据场景输出不同版本：

- **`official`**
  - 正式学生试卷
  - 不显示答案、解析、教师备注等附加层

- **`teacher`**
  - 教师版
  - 显示答案、关键词、来源、教师备注、解析

- **`teacher-redline`**
  - 教师红批版
  - 在教师版基础上，对客观题正确选项进行红色标注

- **`review`**
  - 复习 / 审稿版
  - 显示完整的辅助信息

### 4. 支持的题型

当前支持的题型包括：

- 单项选择题 `single_choice`
- 多项选择题 `multiple_choice`
- 判断题 `judgement`
- 填空题 `fill_blank`
- 简答题 `short_answer`
- 计算题 `calculation`
- 证明题 `proof`
- 编程题 `programming`
- 综合题 `composite`

### 5. 面向打印的版式能力

项目针对试卷排版做了专门处理，支持：

- A4 纵向打印布局
- 标题区、注意事项区、分节标题渲染
- 题号与分节编号规范化
- 代码块缩进保留
- 填空横线保留
- 数学公式渲染
- HTML 中间层检查与 PDF 成品导出

## 目录结构

```text
jiangsu-exam-paper-pdf-generator/
├─ assets/                 # 样例输入与样式文件
├─ build/                  # 临时构建输出
├─ cases/                  # 完整试卷案例
├─ deliverables/           # 已生成的正式交付成果
├─ references/             # schema、排版规则、workflow 文档
├─ scripts/                # 构建脚本
├─ SKILL.md                # 面向 Agent 的 skill 说明
└─ README.md               # 项目说明文档
```

主要目录说明：

- **`assets/`**
  - `example_exam.md`：最小可运行样例
  - `jiangsu_exam.css`：试卷打印样式

- **`scripts/`**
  - `build_exam_paper.py`：主构建脚本
  - `build_exam_paper.ps1`：Windows 下的 PowerShell 包装脚本

- **`cases/`**
  - 存放完整试卷或强化练习的源文件案例

- **`deliverables/`**
  - 存放已经生成的真实交付成果，如 `.json`、`.html`、`.pdf`

- **`references/`**
  - `input-schema.md`：输入结构定义
  - `layout-rules.md`：排版规范
  - `workflow.md`：工作流和验收要点

## 环境依赖

运行本项目前，请准备以下环境：

- **Python**：3.8 或更高版本
- **Pandoc**：2.x 或更高版本
- **PDF 导出引擎**：以下至少一种
  - Google Chrome 或 Microsoft Edge（推荐）
  - wkhtmltopdf（备用）

说明：

- 如果需要正确渲染公式，推荐优先使用 **Chrome / Edge** 的 headless 打印能力
- `wkhtmltopdf` 可作为兜底方案，但公式可能显示为原始 TeX

## 快速开始

### 方式一：使用 PowerShell 包装脚本

```powershell
.\scripts\build_exam_paper.ps1 `
  -InputPath .\assets\example_exam.md `
  -OutputDir .\build `
  -Variant teacher-redline
```

生成完成后，可在 `build/` 目录中看到：

- `example_exam.normalized.json`
- `example_exam.teacher-redline.html`
- `example_exam.teacher-redline.pdf`

### 方式二：直接调用 Python 脚本

```powershell
python scripts/build_exam_paper.py \
  --input assets/example_exam.md \
  --output-dir build \
  --variant teacher-redline
```

也可以显式传入外部程序路径：

```powershell
python scripts/build_exam_paper.py \
  --input assets/example_exam.md \
  --output-dir build \
  --variant teacher-redline \
  --pandoc-path "C:\path\to\pandoc.exe" \
  --chrome-path "C:\path\to\chrome.exe"
```

## 构建脚本说明

### `scripts/build_exam_paper.py`

这是项目的主入口脚本，负责完成以下工作：

1. 读取 Markdown / JSON / YAML 输入
2. 解析并规范化为统一 JSON
3. 渲染 HTML 页面
4. 调用浏览器或 wkhtmltopdf 导出 PDF

支持的主要参数：

- `--input`
- `--output-dir`
- `--variant`
- `--pandoc-path`
- `--chrome-path`
- `--wkhtmltopdf-path`
- `--html-only`
- `--json-only`

### `scripts/build_exam_paper.ps1`

这是 Windows 环境下的便捷包装脚本。

当前它支持：

- `-InputPath`
- `-OutputDir`
- `-Variant`
- `-PandocPath`
- `-PythonPath`

注意：

- 该包装脚本 **不会透传** Python 脚本的全部参数
- 如果你需要 `--html-only`、`--json-only`、自定义 Pandoc 路径、自定义浏览器路径等高级能力，请直接调用 `build_exam_paper.py`
- 包装脚本中的默认 `PythonPath` 是机器相关路径，换环境时可能需要手动指定 `-PythonPath`

## 输入格式说明

### Markdown-first 结构

推荐优先使用 Markdown-first 方式编写试卷。基本结构如下：

1. 文件顶部使用 frontmatter 描述考试元信息
2. 使用 `#` 表示大题分节
3. 使用 `##` 表示具体题目
4. 使用 `@key: value` 表示题目元数据

最小示例：

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

### 常见元数据字段

题目标题下可使用的字段包括：

- `@type`
- `@answer`
- `@keywords`
- `@source`
- `@teacher_note`
- `@analysis`
- `@score`
- `@answer_lines`

更完整的输入规范请参考：

- `references/input-schema.md`

## 输出结果说明

每次构建通常会输出以下文件：

- **`*.normalized.json`**
  - 规范化后的标准数据
  - 适合调试、复查、作为后续流程输入

- **`*.{variant}.html`**
  - 渲染后的 HTML 中间产物
  - 适合检查排版、分页、公式、颜色与结构

- **`*.{variant}.pdf`**
  - 最终交付版本
  - 适合打印、归档或发给使用方

例如：

- `example_exam.normalized.json`
- `example_exam.teacher-redline.html`
- `example_exam.teacher-redline.pdf`

## 已有交付成果

当前仓库中已经包含一批构建成果，可直接作为项目能力证明：

- `build/`
  - `example_exam.normalized.json`
  - `example_exam.teacher-redline.html`
  - `example_exam.teacher-redline.pdf`

- `deliverables/`
  - `zhuanzhuanben-computer-foundation-paper.official.html`
  - `zhuanzhuanben-computer-foundation-paper.official.pdf`
  - `zhuanzhuanben-computer-foundation-paper.teacher-redline.html`
  - `zhuanzhuanben-computer-foundation-paper.teacher-redline.pdf`
  - `zhuanzhuanben-computer-foundation-intensive.official.html`
  - `zhuanzhuanben-computer-foundation-intensive.official.pdf`
  - `zhuanzhuanben-computer-foundation-intensive.teacher-redline.html`
  - `zhuanzhuanben-computer-foundation-intensive.teacher-redline.pdf`

## 常见问题

### 1. 找不到 Pandoc

请先安装 Pandoc，或在命令中显式传入 `--pandoc-path`。

### 2. 无法导出 PDF

请确认系统中至少安装了以下一种工具：

- Chrome / Edge
- wkhtmltopdf

项目会优先尝试 Chrome / Edge，失败后再尝试 wkhtmltopdf。

### 3. 公式在 PDF 中显示异常

如果公式显示为原始 TeX，而不是排版后的数学公式，请改用 Chrome / Edge 导出，而不是 wkhtmltopdf。

### 4. 中文字体显示为方框

请安装支持 CJK 的字体，例如：

- Noto Sans CJK
- Source Han Sans

### 5. `@key` 元数据没有生效

请确保 `@key: value` 行紧跟在 `##` 题目标题下面，中间不要插入空行。

### 6. 需要高级参数，但 `.ps1` 不支持

请直接调用：

```powershell
python scripts/build_exam_paper.py ...
```

## 参考文档

- `SKILL.md`
  - 面向 Agent 的 skill 使用说明

- `references/input-schema.md`
  - 输入结构与字段说明

- `references/layout-rules.md`
  - 版式规则与视觉约束

- `references/workflow.md`
  - 工作流、验收清单与 troubleshooting

## 适用场景总结

这个项目适合以下类型的工作：

- 根据考试大纲快速组织并输出正式试卷
- 将教师整理的题库转换为统一格式与正式成品
- 为同一套试题同时生成学生卷和教师卷
- 为 AI 出题 / 教师审稿 / PDF 交付建立可重复流程

如果你希望把这个项目进一步扩展为更多考试科目或更多排版风格，也可以在现有 schema、样式和构建流程基础上继续演进。

## Chrome / Edge Discovery

When exporting PDF, `scripts/build_exam_paper.py` prefers Chrome or Edge headless printing before falling back to `wkhtmltopdf`.

Browser discovery order:

1. Use `--chrome-path` if it is explicitly provided.
2. Otherwise try executables available in `PATH`:
   - `chrome`
   - `msedge`
3. If neither is found in `PATH`, try these common Windows install paths:
   - `C:\Program Files\Google\Chrome\Application\chrome.exe`
   - `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
   - `C:\Program Files\Microsoft\Edge\Application\msedge.exe`
   - `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`

If all of the above fail, the script will continue trying `wkhtmltopdf`.

Recommended usage when you want stable browser selection:

```powershell
python scripts/build_exam_paper.py \
  --input assets/example_exam.md \
  --output-dir build \
  --variant teacher-redline \
  --pandoc-path "D:\path\to\pandoc.exe" \
  --chrome-path "C:\Program Files\Google\Chrome\Application\chrome.exe"
```
