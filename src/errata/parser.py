"""Parse an error catalog (``06-誤答カタログ.md``) into structured data.

The catalog is one Markdown file:

- YAML front matter with ``type: error-catalog`` and ``created: YYYY-MM-DD``
- ``## 件数の一覧 ...``: a summary table (category, count, first -> latest, status)
- ``## A <title>`` ... ``## L <title>``: one section per weak point.
  A section has an optional ``**規則**：`` line, a list of entries, and a
  ``> [!check]- 正答`` callout with the correct answers.
- ``## まだ答えを見ていない問題``: entries whose answers have not been checked yet.

The parser never stops on a bad line. Problems are collected as ``Issue`` objects
with line numbers, so one typo does not block a report.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from .labels import (
    UNKNOWN,
    Label,
    match_answer_label,
    match_entry_labels,
    resolve_date,
    starts_with_label,
)

PENDING_SECTION = "まだ答えを見ていない問題"
SUMMARY_SECTION = "件数の一覧"

_CATEGORY_HEADING = re.compile(r"^## (?P<id>[A-Z]) (?P<title>.+?)\s*$")
_RULE = re.compile(r"^\*\*規則\*\*\s*[：:]\s*(?P<rule>.+?)\s*$")
_BULLET = re.compile(r"^- (?P<text>.+?)\s*$")
_CHECK_CALLOUT = re.compile(r"^>\s*\[!check\][-+]?\s*正答")
_MEMO = re.compile(r"（(?P<memo>[^（）]*)）\s*$")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_REPEAT = re.compile(r"(\d+)回目")
_TABLE_ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
_OPEN = "（("
_CLOSE = "）)"


def split_outside_parens(text: str, sep: str) -> list[str]:
    """Split ``text`` on ``sep``, but not inside （…） or (…)."""
    parts: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth = max(depth - 1, 0)
        elif ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def split_before_labels(text: str, sep: str) -> list[str]:
    """Split on ``sep`` (outside parentheses) only where a label follows it.

    Other separators stay in the text, so "prefer / rather" or a "／" inside a
    sentence is not cut.
    """
    segments: list[str] = []
    for part in split_outside_parens(text, sep):
        if segments and not starts_with_label(part.strip()):
            segments[-1] += sep + part
        else:
            segments.append(part)
    return [s.strip() for s in segments]


@dataclass
class Issue:
    line: int
    level: Literal["error", "warning"]
    code: str
    message: str


@dataclass
class Entry:
    category_id: str | None  # None for the pending section
    label: Label
    text: str  # sentence as written, with ** markers removed
    error_parts: list[str]  # the parts written in bold
    memo: str | None
    repeat: int | None  # "5回目" in the memo -> 5
    line: int
    date: date | None = None
    answer: str | None = None
    answer_line: int | None = None

    @property
    def entry_id(self) -> str:
        """Stable ID: the same label and sentence always give the same ID."""
        key = f"{self.label.key}\n{' '.join(self.text.split())}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


@dataclass
class Category:
    id: str
    title: str
    line: int
    rule: str | None = None
    entries: list[Entry] = field(default_factory=list)


@dataclass
class SummaryRow:
    category_id: str
    title: str
    count: int | None
    line: int


@dataclass
class Catalog:
    path: Path | None
    created: date | None
    categories: dict[str, Category] = field(default_factory=dict)
    pending: list[Entry] = field(default_factory=list)
    summary: list[SummaryRow] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def entries(self) -> list[Entry]:
        result = [e for c in self.categories.values() for e in c.entries]
        return result + self.pending

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)


# ---------------------------------------------------------------------------


def parse_file(path: Path) -> Catalog:
    catalog = parse_text(path.read_text(encoding="utf-8"))
    catalog.path = path
    return catalog


def parse_text(text: str) -> Catalog:
    lines = text.splitlines()
    catalog = Catalog(path=None, created=None)
    start = _parse_front_matter(lines, catalog)
    _Parser(catalog).run(lines, start)
    _check_summary(catalog)
    catalog.issues.sort(key=lambda i: i.line)
    return catalog


def _parse_front_matter(lines: list[str], catalog: Catalog) -> int:
    """Read the front matter. Returns the index of the first body line."""
    if not lines or lines[0].strip() != "---":
        catalog.issues.append(
            Issue(1, "warning", "no-front-matter", "No front matter; dates cannot get a year")
        )
        return 0
    meta: dict[str, str] = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i + 1
            break
        key, sep, value = lines[i].partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    else:
        catalog.issues.append(Issue(1, "error", "front-matter-open", "Front matter is not closed"))
        return 0

    if meta.get("type") != "error-catalog":
        catalog.issues.append(
            Issue(1, "warning", "front-matter-type", "Front matter type is not 'error-catalog'")
        )
    created = meta.get("created")
    if created:
        try:
            catalog.created = date.fromisoformat(created)
        except ValueError:
            catalog.issues.append(
                Issue(1, "warning", "front-matter-created", f"Bad created date: {created!r}")
            )
    else:
        catalog.issues.append(
            Issue(1, "warning", "front-matter-created", "No created date; dates cannot get a year")
        )
    return end


class _Parser:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.section: Literal["none", "summary", "category", "pending", "other"] = "none"
        self.category: Category | None = None
        self.entries: list[Entry] = []
        self.answers: list[tuple[str, str, int]] = []  # (label key, answer, line)
        self.in_callout = False
        self.exercise: str | None = None  # last exercise seen in the current callout

    # -- helpers ------------------------------------------------------------

    def issue(self, line: int, level: Literal["error", "warning"], code: str, msg: str) -> None:
        self.catalog.issues.append(Issue(line, level, code, msg))

    # -- main loop ----------------------------------------------------------

    def run(self, lines: list[str], start: int) -> None:
        for index in range(start, len(lines)):
            self.line(lines[index], index + 1)
        self.close_section()

    def line(self, raw: str, no: int) -> None:
        if raw.startswith("## "):
            self.close_section()
            self.open_section(raw, no)
            return

        if self.in_callout:
            if raw.startswith(">"):
                self.answer_line(raw, no)
                return
            self.in_callout = False

        stripped = raw.strip()
        if not stripped or stripped == "---" or raw.startswith("# "):
            return

        if self.section == "summary":
            self.summary_line(stripped, no)
        elif self.section in ("category", "pending"):
            self.body_line(raw, no)

    def open_section(self, raw: str, no: int) -> None:
        heading = raw[3:].strip()
        m = _CATEGORY_HEADING.match(raw)
        if m:
            cid = m.group("id")
            if cid in self.catalog.categories:
                self.issue(no, "error", "duplicate-category", f"Category {cid} appears twice")
            self.category = Category(id=cid, title=m.group("title"), line=no)
            self.catalog.categories[cid] = self.category
            self.section = "category"
        elif heading.startswith(SUMMARY_SECTION):
            self.section = "summary"
        elif heading.startswith(PENDING_SECTION):
            self.section = "pending"
        else:
            self.section = "other"

    def close_section(self) -> None:
        if self.section in ("category", "pending"):
            self.pair_answers()
        self.section = "none"
        self.category = None
        self.entries = []
        self.answers = []
        self.in_callout = False

    # -- section body -------------------------------------------------------

    def body_line(self, raw: str, no: int) -> None:
        m = _RULE.match(raw)
        if m and self.category is not None:
            self.category.rule = m.group("rule")
            return
        if _CHECK_CALLOUT.match(raw):
            self.in_callout = True
            self.exercise = None
            return
        m = _BULLET.match(raw)
        if m:
            self.entry_line(m.group("text"), no)

    def entry_line(self, text: str, no: int) -> None:
        """One bullet line. It may hold several mistakes:

        - "54.1 #12 … ／ #13 … ／ 54.3 2b …": split on "／" where a label follows;
          an item number alone reuses the exercise before it.
        - "70.4 #3・#5 …": one entry per item. If the text has exactly one
          "／"-separated part per item, the parts go to the items in order;
          otherwise every item gets the whole text.
        """
        if match_entry_labels(text, None) is None:
            self.issue(no, "warning", "unknown-label", f"Unrecognized source label: {text[:30]!r}")
            self.add_entry(UNKNOWN, text, no)
            return

        exercise: str | None = None
        for segment in split_before_labels(text, "／"):
            matched = match_entry_labels(segment, exercise)
            if matched is None:  # cannot happen: split only before labels
                self.issue(
                    no, "warning", "unknown-label", f"Unrecognized source label: {segment[:30]!r}"
                )
                continue
            labels, rest = matched
            exercise = labels[-1].exercise
            parts = split_outside_parens(rest, "／")
            if len(labels) > 1 and len(parts) == len(labels):
                for label, part in zip(labels, parts, strict=True):
                    self.add_entry(label, part.strip(), no)
            else:
                for label in labels:
                    self.add_entry(label, rest, no)

    def add_entry(self, label: Label, rest: str, no: int) -> None:
        memo = None
        m = _MEMO.search(rest)
        if m:
            memo = m.group("memo")
            rest = rest[: m.start()].rstrip()

        error_parts = _BOLD.findall(rest)
        sentence = rest.replace("**", "").strip()
        if not sentence:
            self.issue(no, "error", "empty-entry", "Entry has a label but no sentence")
            return
        if not error_parts:
            self.issue(no, "warning", "no-bold", "No **bold** part marks the mistake")

        repeat = None
        if memo:
            r = _REPEAT.search(memo)
            if r:
                repeat = int(r.group(1))

        entry_date = None
        if label.month_day and self.catalog.created:
            entry_date = resolve_date(label.month_day, self.catalog.created)
            if entry_date is None:
                self.issue(no, "warning", "bad-date", f"Impossible date in label {label.raw!r}")

        entry = Entry(
            category_id=self.category.id if self.category else None,
            label=label,
            text=sentence,
            error_parts=error_parts,
            memo=memo,
            repeat=repeat,
            line=no,
            date=entry_date,
        )
        self.entries.append(entry)
        if self.category is not None:
            self.category.entries.append(entry)
        else:
            self.catalog.pending.append(entry)

    def answer_line(self, raw: str, no: int) -> None:
        content = raw.lstrip(">").strip()
        if not content:
            return
        segments = [
            piece
            for part in split_outside_parens(content, "／")
            for piece in split_before_labels(part, "・")
        ]
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            matched = match_answer_label(segment, self.exercise)
            if matched is None:
                self.issue(
                    no,
                    "warning",
                    "unknown-answer-label",
                    f"Unrecognized label in answer: {segment[:30]!r}",
                )
                continue
            label, answer = matched
            self.exercise = label.exercise
            if not answer:
                self.issue(no, "warning", "empty-answer", f"No answer after label {label.raw!r}")
                continue
            self.answers.append((label.key, answer.strip(), no))

    def pair_answers(self) -> None:
        """Attach each answer to the first unanswered entry with the same label."""
        for key, answer, no in self.answers:
            target = next(
                (e for e in self.entries if e.label.key == key and e.answer is None), None
            )
            if target is None:
                self.issue(no, "warning", "orphan-answer", f"Answer has no matching entry: {key!r}")
                continue
            target.answer = answer
            target.answer_line = no

        if self.section == "category":
            for e in self.entries:
                if e.answer is None:
                    self.issue(
                        e.line,
                        "warning",
                        "no-answer",
                        f"No answer found for {e.label.key or e.text[:30]!r}",
                    )

    # -- summary table ------------------------------------------------------

    def summary_line(self, line: str, no: int) -> None:
        m = _TABLE_ROW.match(line)
        if not m:
            return
        cells = [c.strip() for c in m.group("cells").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            return  # separator row
        head = re.match(r"^(?P<id>[A-Z]) (?P<title>.+)$", cells[0])
        if not head:
            return  # header row or a row without a category ID
        count = None
        if len(cells) > 1:
            try:
                count = int(cells[1])
            except ValueError:
                self.issue(no, "warning", "summary-count", f"Count is not a number: {cells[1]!r}")
        self.catalog.summary.append(SummaryRow(head.group("id"), head.group("title"), count, no))


def _check_summary(catalog: Catalog) -> None:
    """Compare the summary table with the sections that were actually found."""
    if not catalog.summary:
        return
    listed = {row.category_id for row in catalog.summary}
    for row in catalog.summary:
        category = catalog.categories.get(row.category_id)
        if category is None:
            catalog.issues.append(
                Issue(
                    row.line,
                    "warning",
                    "summary-missing-section",
                    f"Category {row.category_id} is in the summary but has no section",
                )
            )
        elif row.count is not None and row.count != len(category.entries):
            catalog.issues.append(
                Issue(
                    row.line,
                    "warning",
                    "summary-count-mismatch",
                    f"Category {row.category_id}: summary says {row.count}, "
                    f"section has {len(category.entries)}",
                )
            )
    for cid, category in catalog.categories.items():
        if cid not in listed:
            catalog.issues.append(
                Issue(
                    category.line,
                    "warning",
                    "section-not-in-summary",
                    f"Category {cid} has a section but is not in the summary",
                )
            )
