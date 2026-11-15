# errata

**Turn your English error catalog into weak-point reports and Anki cards.**

`errata` is a command-line tool for self-directed English learners who collect their
mistakes in a Markdown "error catalog" (for example, in an Obsidian vault). It reads
the catalog, checks that every mistake has a correct answer, shows which weak points
keep coming back, and (soon) writes weekly reports and Anki cards.

> Status: early development. v0.1 (`scan`) works; other commands are planned.

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
  separated by `／`.
- Optional sections: `## 件数の一覧` (summary table, checked against the sections) and
  `## まだ答えを見ていない問題` (mistakes not yet checked; no answer needed).

Supported source labels:

| Label | Meaning |
|---|---|
| `60.1 #8`, `64.4 2c` | Grammar workbook exercise and item |
| `126 左ページ B の例文` | Example sentence in the workbook |
| `10/20 Speak`, `10/6 Speak レベル測定` | Conversation app session |
| `10/3 混合 (4)`, `10/17 混合 英作文 (A)` | Weekly mixed test |
| `9/18 1分タスク`, `11/10 1分タスク (1)` | Daily one-minute task |

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

## Development

```bash
git clone https://github.com/<you>/errata.git
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
