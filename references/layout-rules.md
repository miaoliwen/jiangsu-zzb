# Layout Rules

These rules are based on the sample Jiangsu专转本 computer exam pages provided by the user.

## Page Setup

- A4 portrait
- Print margins close to standard exam paper proportions
- Top-left confidential label block
- Centered title block with bold title and smaller subtitle

## Typography

- Chinese body text should read like a formal printed test paper, not a marketing document
- Title uses bold, centered layout
- Section headings use bold black text
- Question stems and question numbers use light blue by default
- Answer/teacher overlays are not part of the formal paper body
- In `teacher-redline`, correct answers for objective questions may be highlighted in red

## Section Layout

- Section headings follow the pattern `一、单项选择题`
- Section description appears on the same line or the immediately following line
- Questions are numbered continuously across the whole paper

## Question Layout

- Objective questions:
  - stem in light blue
  - options in black
  - two-column layout is applied **automatically by the CSS** when all options are short enough; no render flag is needed and no author action is required
- Judgement questions:
  - render the statement only
  - section description carries the A/B answer-card instruction
- Fill-in-the-blank questions:
  - preserve answer lines
- Subjective questions:
  - preserve paragraph spacing
  - preserve displayed formulas
  - preserve code indentation

## Teacher Overlay Rules

The user clarified that the following are later-added layers:

- answers
- keywords
- red emphasis
- source references
- teacher notes

That means:

- `official` must hide them all
- `teacher` and `review` may show them
- `teacher-redline` may additionally color correct objective answers red

## Pagination Rules

- Avoid splitting a question stem from all of its options if possible
- Avoid splitting answer blocks from the question they belong to
- Use generous line-height for legibility
- Keep code blocks and formula blocks together when possible

