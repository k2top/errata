# errata

**Turn your English error catalog into weak-point reports and Anki cards.**

`errata` is a command-line tool for self-directed English learners who collect their
mistakes in a Markdown "error catalog" (for example, in an Obsidian vault). It reads
the catalog, checks that every mistake has a correct answer, shows which weak points
keep coming back, and (soon) writes weekly reports and Anki cards.

> Status: v0.1 (`scan`) is done and is used on a real catalog of about 500 mistakes.
> Other commands are planned.

## Why

Keeping an error catalog is easy. Keeping it correct and learning from it is harder:

- Answers are kept apart from the mistakes, so it is easy to forget one.
- The summary table at the top gets out of date when new mistakes are added.
- It is hard to see which mistakes are one-off and which ones keep repeating.
- Making Anki cards by hand takes time, and it is easy to add the same card twice.

`errata` does the checking and counting, so the learner can focus on the mistakes.

## Commands

| Command | Status | What it does |
|---|---|---|
| `errata scan` | v0.1 | Parse the catalog and list problems with line numbers |
| `errata stats` | planned | Count mistakes by category and by week |
| `errata report --week` | planned | Write a weekly Markdown report into the vault |
| `errata anki` | planned | Export new cards as Anki TSV, without duplicates |

## Catalog format

One Markdown file with one section per weak point. Mistakes are listed with a source
label, and the correct answers go in a folded callout at the end of the section:

```markdown
---
type: error-catalog
created: 2026-09-18
---

## A 動詞ごとの前置詞

**規則**：動詞のあとの前置詞は動詞ごとに決まっている。

- 60.1 #8 I'm looking forward to **meet** the new team
- 10/20 Speak we **discussed about** the schedule
- 11/15 混合 (4) This manual is too hard **to me**.（for・5回目）

> [!check]- 正答
> 60.1 #8 meeting
> 10/20 Speak：we discussed the schedule
> 11/15 混合 (4)：It's too hard for me.
```

- `## A <title>`: the letter is the category ID.
- Each list item starts with a **source label**, then the sentence as written. The
  mistake is in `**bold**`. An optional note goes in full-width parentheses at the end.
- Answers are matched to mistakes by their label. Several answers can share one line,
  separated by `／` (a `／` inside parentheses does not count).
- One list item can hold several mistakes, separated by `／`: `54.1 #12 … ／ #13 …`,
  or `10/27 Speak A ／ B` for two mistakes in one session. `70.4 #3・#5` gives one entry
  per item.
- An answer may leave out the label or the item number: `10/20 Speak：a ／ b`,
  `11/10 1分タスク：…`, `96.3：a ／ b`. Such answers are matched in the order they are
  written, and marked `answer_by_order` in the JSON output. The rules are in
  [DESIGN.md 4.1](docs/DESIGN.md#41-answers-with-a-short-label-or-no-label).
- Optional sections: `## 件数の一覧` (summary table, checked against the sections) and
  `## まだ答えを見ていない問題` (mistakes not yet checked; no answer needed).

Supported source labels:

| Label | Meaning |
|---|---|
| `60.1 #8`, `64.4 2c` | Grammar workbook exercise and item |
| `126 左ページ B の例文`, `10/27 左ページの例文` | Example sentence in the workbook |
| `10/20 Speak`, `10/6 Speak レベル測定` | Conversation app session |
| `10/3 混合 (4)`, `10/17 混合 英作文 (A)` | Weekly mixed test |
| `9/18 1分タスク`, `11/10 1分タスク (1)`, `9/18夜 1分タスク(1)` | Daily one-minute task |
| `10/9 想起`, `10/13 前日の想起` | Recall of an earlier sentence |
| `11/4 言い直し 100.3 #2`, `10/31 言い直し (9)` | Second try after checking |
| `10/10 英作文 (A)`, `10/13 Anki` | Composition, Anki review |

A label is read as a row of parts (date, exercise, unit, kind word, number), so these
can be combined. A `（…）` right after the label is kept as context, not as part of the
sentence. See [DESIGN.md 4.2](docs/DESIGN.md#42-parts-of-a-label).

Labels with a date have no year; the year comes from `created` in the front matter.

See [`examples/vault/`](examples/vault/) for a full sample. All example sentences in
this repository are original; no textbook content is included.

## Usage

```console
$ errata scan examples/vault/06-誤答カタログ.md
examples/vault/06-誤答カタログ.md  (created 2026-09-18)

ID  entries answered  title
A         3        3  動詞ごとの前置詞
D         2        2  a が要らない名詞に a（不可算・複数）
F         3        3  時制の一致
-         1           (not checked yet)

9 entries in 3 categories

No problems found.
```

- `--json` prints every entry (label, date, sentence, bold parts, note, answer) as JSON.
- `--strict` exits with status 1 when there are warnings, for use in scripts and CI.

Examples of problems `scan` reports: a mistake with no answer, an answer with no
matching mistake, an unrecognized label, a missing `**bold**` part, and a summary
table count that does not match its section.

## How it was built

The parser was first written from a small sample, then fitted to the real catalog it
is meant for. The real catalog is never committed; all examples and tests use
sentences written for this repository.

Each change followed the same steps: write the rule in [DESIGN.md](docs/DESIGN.md),
add a test that fails, change the code, run ruff and pytest, then scan the real
catalog again and compare the warnings by type.

| Step | Warnings | Mistakes with an answer |
|---|---:|---:|
| First version, from the sample | 760 | — |
| Item numbers that reuse the exercise (`／ #6`), `(1)` without a space | 727 | 116 of 433 |
| `／` inside parentheses; several mistakes on one line | 730 | 125 of 458 |
| Answers with a short label or no label (DESIGN 4.1) | 399 | 229 of 479 |
| Labels read as parts; recall, second try and other sources (DESIGN 4.2) | 179 | 353 of 485 |

The number of mistakes goes up because one line with several mistakes is now read as
several entries. This also brought the summary table closer: the learner counts each
mistake in that table, and mismatches fell from 7 to 5.

The remaining warnings are mostly lines of answers written with no label at all, and
answers that are really missing; they have not all been checked one by one. Matching
by order is the weak point: in a random check of 20 such pairs, 19 were right, and the
wrong one sat on a line that also had an `orphan-answer` warning.

**Use of AI.** The code was written with Claude Code (Anthropic) as a pair programmer;
commits it helped write carry a `Co-Authored-By` line. The learner who keeps the
catalog set the goals, the order of work and the method above, and reviewed the rules.
The AI read the real catalog, proposed the rules and wrote the code and tests. Its
output was not taken as correct until the tests and the rescan of the real catalog
agreed with it, and its reports state what was checked and what was not.

## Development

```bash
git clone https://github.com/k2top/errata.git
cd errata
uv sync
uv run pytest
uv run ruff check .
uv run errata scan examples/vault/06-誤答カタログ.md
```

Requires Python 3.11+. No runtime dependencies. See [`docs/DESIGN.md`](docs/DESIGN.md)
for the architecture and the roadmap.

## License

MIT
