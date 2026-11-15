# errata — Design Notes

## 1. Goals and non-goals

**Goals**
- Read the learner's existing error catalog as it is written today. The tool adapts to
  the file, not the other way around.
- Catch bookkeeping mistakes early: missing answers, mismatched labels, an outdated
  summary table.
- Find repeated mistakes by category and over time.
- Produce output the learner actually uses: a weekly report in the vault, and Anki cards
  in the TSV format already used for the grammar deck.
- Be safe with the learner's files: never modify the catalog; write only to explicit
  output paths.

**Non-goals (for v0.x)**
- No GUI or Obsidian plugin.
- No automatic correction of English. The correct answer comes from the catalog.
- No cloud service. Everything runs locally.

## 2. Inputs

| Input | Used from | Notes |
|---|---|---|
| Error catalog (`06-誤答カタログ.md`) | v0.1 | Main input. One file, sections A–L |
| Anki TSV header format | v0.4 | Output format to match, not an input |
| Daily unit pages (`(YYYY-MM-DD) Unit NN 左.md`) | later | Format is not fixed yet; could give dates to workbook labels |
| Anki collection export (`.colpkg`) | later | Already analyzed by a separate script; could be joined by category |

## 3. Data model

```
Catalog   path, created, categories{id -> Category}, pending[Entry], summary[SummaryRow], issues[Issue]
Category  id ("A"), title, rule, entries[Entry], line
Entry     category_id, label, text, error_parts, memo, repeat, date, answer, line,
          answer_by_order (see 4.1)
Label     raw, kind (exercise | example | speak | mixed-test | daily-task | unknown),
          unit, month_day
Issue     line, level (error | warning), code, message
```

- `Entry.text` is the sentence with `**` removed; `error_parts` are the bold parts.
- `Entry.repeat` comes from a memo such as `（…・5回目・…）`.
- `Entry.date` is resolved from `M/D` labels using the catalog's `created` date: a date
  more than 60 days before `created` is taken to be in the next year. Workbook labels
  have no date (`None`).
- `Entry.entry_id` = first 12 hex digits of SHA-1 of (label key, normalized sentence).
  It is stable across runs, so Anki export can avoid duplicates.

## 4. Parsing rules

The parser is a line-based state machine. It never stops on a bad line; it records an
`Issue` with a line number and continues.

| Line | Action |
|---|---|
| `## <A-Z> <title>` | Start a category section |
| `## 件数の一覧…` | Start the summary table |
| `## まだ答えを見ていない問題` | Start the pending section (answers not required) |
| other `## …` | Ignored section |
| `**規則**：…` | Rule of the current category |
| `- <label> <sentence>（memo）` | Entry |
| `> [!check]- 正答` | Start of answers; following `>` lines are answers |
| `> <label>：answer ／ <label> answer` | One or more answers, split on `／` outside parentheses |
| `- 54.1 #12 … ／ #13 … ／ 54.3 2b …` | Several entries on one line: split on every full-width `／` outside parentheses; an item number alone reuses the exercise before it |
| `- 10/27 Speak A ／ B` | A part with no label is another entry with the label of the part before it (two mistakes in one session). The half-width `/` (`prefer / rather`) is not a separator |
| `- 70.4 #3・#5 …` | One entry per item. If the parts with no label after it number exactly one per item, they go to the items in order; otherwise every item gets the whole text |
| `> 141.1 #2 b・#3 c` | In answers, `・` followed by a label also separates answers |

**Pairing answers:** at the end of a section, each answer is attached to the first
unanswered entry with the same normalized label. This handles two entries with the
same label (for example, two mistakes in one Speak session) as long as the answers are
written in the same order.

### 4.1 Answers with a short label or no label

The learner often writes the answer with less detail than the entry. Real examples
(sentences replaced):

| Entry side | Answer side | Shortened part |
|---|---|---|
| `- 10/20 Speak A` / `- 10/20 Speak B` | `> 10/20 Speak：a ／ b` | Label of the 2nd answer |
| `- 11/10 1分タスク(1) …` | `> 11/10 1分タスク：…` | Item number |
| `- 96.3 #4 … ／ #6 …` | `> 96.3：a ／ b` | Item number, then the whole label |
| `- 10/24 混合 (6)`, `(9)`, `英作文 (A)` | `> 10/24 混合：a ／ b ／ 英作文 (A)：c` | Item numbers |

In every example checked in the real catalog, these answers are in the same order as
the entries. The rules below rely on that.

**Fields of a label.** A label is read into fields: date (`month_day`), kind, unit,
exercise (`96.3`), and item (`#4`, `(1)`, `(A)`, `英作文 (A)`). Words such as
`英作文` belong to the item, not to the kind.

**Full and short answer labels.**
- An answer label is *full* if its key equals the key of some entry in the section.
- Otherwise it is *short*. A short label *covers* an entry when every field the short
  label gives is equal to the entry's field. Fields the short label leaves out can be
  anything. Examples: `11/10 1分タスク` covers `11/10 1分タスク (1)` and `(2)`;
  `96.3` covers `96.3 #4` and `96.3 #6`.

**Group (the label carried to the next answer).** Each answer leaves a group that the
next answer without a label uses:
- After a full label with an item, the group is that label without the item
  (`96.3 #4` → `96.3`; `10/3 混合 (4)` → `10/3 混合`).
- After a full label without an item (`10/20 Speak`), or after a short label, the group
  is that label.
- An answer with no label is read as a short label equal to the group.
- The group is kept to the end of the callout, across `>` lines, like the exercise for
  `#6` today. It is cleared at each new `> [!check]- 正答`.
- An answer with no label and no group is reported as `unknown-answer-label`, as now.
- A part that looks like a label we cannot read (a short prefix before `：`, such as
  `想起：` or `130：`) is reported as `unknown-answer-label` and does not take the group.
  The answers after it on the line belong to that unknown label and are skipped
  without another warning.

**Two-pass pairing** (at the end of a section):
1. Full labels first, with the existing rule (same key, first unanswered entry).
   This runs first so a short answer cannot take an entry that has its own full
   answer later in the callout (the `10/24 混合` example).
2. Short labels and answers without a label, in the order they are written: each is
   attached to the first unanswered entry, in entry order, that the label covers.
   Entries attached this way get `Entry.answer_by_order = True`, so a report can show
   how many pairs depend on order.

If a short answer covers no unanswered entry, it is `orphan-answer`. If entries are
left, they are `no-answer`. Both are the existing warnings, and a wrong count of
answers shows up as one of them. A pair in the wrong order is not detected; this is
the cost of these rules.

**Notes in a callout.** A `>` line whose content starts with `**` is a note (for
example, a summary of the mistakes in the section). It is skipped without a warning
and does not change the group.

**Not covered here.**
- New label forms are handled in item (5): `想起`, `言い直し`, `10/9夜`, `Speak` with no
  date, and a unit alone (`130：`). Once (5) adds them, they are short labels under the
  same rules.
- An answer more detailed than its entry (entry `11/10 1分タスク`, answer
  `11/10 1分タスク (1)`) is not matched. It stays `orphan-answer`, because this form has
  not been seen.
- Ranges such as `72.3 #7〜10`.

**Label recognition** uses an ordered list of regular expressions (`labels.py`). The
label must be recognized by pattern because some labels contain ASCII words (`Speak`,
`B`), so "everything before the first English word" does not work. Unknown labels are
kept as entries with kind `unknown` and reported as warnings.

**Issue codes (v0.1):** `no-answer`, `orphan-answer`, `unknown-label`,
`unknown-answer-label`, `empty-answer`, `no-bold`, `empty-entry`, `bad-date`,
`summary-count-mismatch`, `summary-missing-section`, `section-not-in-summary`,
`summary-count`, `duplicate-category` (error), front-matter issues.

## 5. Architecture

```
src/errata/
  labels.py     # label patterns, Label, resolve_date
  parser.py     # catalog -> Catalog + issues
  cli.py        # argparse: scan (v0.1), more commands later
  (store.py)    # v0.2: SQLite history of entries and Anki exports
  (analysis.py) # v0.2: counts by category and by week, repeat offenders
  (report.py)   # v0.3: weekly Markdown report
  (anki.py)     # v0.4: card selection and TSV export
tests/
examples/vault/ # sample catalog, used by README, tests and CI
```

## 6. Key decisions

| Topic | Decision | Reason |
|---|---|---|
| Language | Python 3.11+ | Good text handling; stdlib `sqlite3` and `tomllib` |
| Dependencies | None at runtime (argparse, stdlib only) | Easy to install anywhere |
| Packaging | uv + `pyproject.toml` | Fast, reproducible |
| Quality | pytest, ruff (lint + format), GitHub Actions on 3.11–3.13 | CI on every push |
| Parse errors | Report and continue | One typo should not block a report |
| Summary table | Read only, compared with sections | The tool never edits the catalog |

## 7. Anki export (v0.4 plan)

Match the TSV format already used for the grammar deck:

```
#separator:tab
#html:true
#notetype:基本
#deck:英語::誤答
#tags:errata
<front>	<back>	<tags>
```

- Front: the learner's sentence with the mistake in `<b>…</b>`, plus the source label.
- Back: the correct answer, `<br>`, the category rule.
- Tags: category ID and source kind, e.g. `cat::A src::mixed-test`.
- Default limit: 3 new cards per day. Repeated mistakes (`repeat` ≥ 2) first, then newest.
- Export history is stored in SQLite by `entry_id`, so a card is never exported twice.

## 8. Roadmap

| Version | Scope | Done when |
|---|---|---|
| v0.1 | Catalog parser, `scan`, sample vault, tests, CI | Sample parses with 0 issues; each problem type is reported with the right line |
| v0.2 | `stats`: counts by category and by week; `errata.toml` config | Weekly counts match a hand count on the sample |
| v0.3 | `report --week` | Report is written to the vault; re-running the same week overwrites, not appends |
| v0.4 | `anki` with SQLite export history | Running `anki` twice exports no duplicates |
| v0.5 | Join with Anki review data (fail rate by category) | One report shows both catalog and review weak points |
| later | Read daily unit pages to date workbook labels; optional LLM category suggestions (off by default) | — |

## 9. Privacy and content rules

- The real vault is never committed. `.gitignore` excludes `*.tsv`, `*.db`, `*.colpkg`,
  `/vault/`, and `errata.toml`.
- Example sentences are written from scratch. Do not copy textbook exercises or answers.
- No API keys in the repository. Optional LLM features read keys from environment variables.
