"""Source labels: the short prefix that says where a mistake came from.

Examples of labels found at the start of an entry or an answer:

    60.1 #8              exercise 60.1, item 8 (grammar workbook)
    64.4 2c              exercise 64.4, item 2c
    126 左ページ B の例文  example sentence B on the left page of unit 126
    10/20 Speak          conversation app, Oct 20
    10/6 Speak レベル測定  conversation app level check, Oct 6
    10/3 混合 (4)         weekly mixed test, question 4
    10/17 混合 英作文 (A)  weekly mixed test, composition A
    11/10 1分タスク (1)   daily one-minute task, item 1
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# Kind words, longest first within a family (DESIGN.md 4.2).
KIND_WORDS: dict[str, str] = {
    "前日の想起の例文": "recall",
    "前日の想起の規則": "recall",
    "前日の想起": "recall",
    "想起の例文": "recall",
    "想起": "recall",
    "採点後の言い直し": "redo",
    "言い直し": "redo",
    "左ページの例文": "example",
    "左ページ例文": "example",
    "右ページの例文": "example",
    "右ページ例文": "example",
    "左ページ": "example",
    "右ページ": "example",
    "の例文": "example",
    "例文": "example",
    "1分タスク": "daily-task",
    "Speak": "speak",
    "混合": "mixed-test",
    "英作文": "composition",
    "Anki": "anki",
}

# Every part of a label must end here.
_END = r"(?=[\s：:（「(]|$)"
_DATE = re.compile(r"(?P<m>\d{1,2})/(?P<d>\d{1,2})夜?" + _END)
_EXERCISE_PART = re.compile(r"(?P<unit>\d{1,3})\.\d{1,2}" + _END)
_ITEM = re.compile(r"#?\d{1,3}[a-z]?" + _END)
_UNIT = re.compile(r"\d{1,3}" + _END)
_KIND = re.compile(
    "(?:" + "|".join(re.escape(w) for w in sorted(KIND_WORDS, key=len, reverse=True)) + ")" + _END
)
_LETTER = re.compile(r"[A-Z]" + _END)
_NUMBER = re.compile(r" ?\([^)\s]+\)" + _END)
_QUALIFIER = re.compile(r"[^\sA-Za-z0-9()（）：:「」]+" + _END)
_COLON = re.compile(r"\s*[：:]")

# An item number alone, e.g. "#6" or "3a", written after "／" to reuse the exercise before it.
_ITEM_ONLY = re.compile(r"(?:#\d{1,3}[a-z]?|\d{1,3}[a-z])(?=[\s：:]|$)")
# Items joined with "・", e.g. "70.4 #3・#5": one mistake line for several items.
# The exercise part is optional when it can be taken from earlier on the line.
_JOINED = re.compile(
    r"(?:(?P<ex>\d{1,3}\.\d{1,2}) )?"
    r"(?P<items>#?\d{1,3}[a-z]?(?:・#?\d{1,3}[a-z]?)+)(?=[\s：:]|$)"
)

# Separators allowed between a label and the text that follows it.
_AFTER_LABEL = re.compile(r"\s*[：:]?\s*")


@dataclass(frozen=True)
class Label:
    raw: str
    kind: str  # see KIND_WORDS; also exercise, any, unknown
    unit: int | None = None
    month_day: tuple[int, int] | None = None
    # The label without its item: "60.2" for "60.2 #5", "10/24 混合" for
    # "10/24 混合 英作文 (A)". None when the label has no item.
    base: str | None = None

    @property
    def key(self) -> str:
        """Normalized form used to pair an entry with its answer.

        Extra spaces are ignored, and "1分タスク(1)" is the same as "1分タスク (1)".
        """
        return re.sub(r"\s*\(", " (", " ".join(self.raw.split()))

    @property
    def exercise(self) -> str | None:
        """For an exercise label such as "60.2 #5", the exercise part "60.2"."""
        return (self.base or self.raw) if self.kind == "exercise" else None

    @property
    def item_prefix(self) -> str | None:
        """The label without a final item number, for an item written alone after it.

        "54.1 #12" -> "54.1"; "10/21 言い直し 141.4 #3" -> "10/21 言い直し 141.4".
        """
        head, _, last = self.raw.rpartition(" ")
        return head if head and _ITEM_ONLY.fullmatch(last) else None

    @property
    def has_item(self) -> bool:
        return self.base is not None

    @property
    def group(self) -> Label:
        """The label without its item; an answer with no label uses it (DESIGN.md 4.1)."""
        if self.base is None:
            return self
        return Label(raw=self.base, kind=self.kind, unit=self.unit, month_day=self.month_day)

    def covers(self, other: Label) -> bool:
        """True if this (answer) label fits the entry label ``other``.

        A label with an item fits only the same label. A label without an item fits
        every label whose fields agree with the fields it gives.
        """
        if self.has_item:
            # "10/24 英作文 (A)" fits "10/24 混合 英作文 (A)": same date, and every
            # part of this label is a part of the other.
            return self.month_day == other.month_day and set(self.key.split()) <= set(
                other.key.split()
            )
        return (
            self.kind in ("any", other.kind)
            and (self.month_day is None or self.month_day == other.month_day)
            and (self.unit is None or self.unit == other.unit)
            and (self.exercise is None or self.exercise == other.exercise)
        )


UNKNOWN = Label(raw="", kind="unknown")


def match_label(text: str) -> tuple[Label, str] | None:
    """Match a label at the start of ``text`` (DESIGN.md 4.2).

    The label is read as a row of parts separated by one space. Returns the label and
    the remaining text (with a ``：`` separator removed), or ``None``.
    """
    month_day = unit = None
    kind: str | None = None
    has_exercise = False
    base_end: int | None = None
    prev = ""  # type of the part before
    pos = 0

    m = _DATE.match(text)
    if m:
        month_day = (int(m.group("m")), int(m.group("d")))
        pos, prev = m.end(), "date"

    while True:
        if kind is not None:
            m = _NUMBER.match(text, pos)
            if m:
                pos, prev = m.end(), "number"
                continue
        start = pos + 1 if pos > 0 else 0
        if pos > 0 and not text.startswith(" ", pos):
            break
        if prev == "exercise":
            m = _ITEM.match(text, start)
            if m:
                pos, prev = m.end(), "item"
                continue
            if text.startswith("#", start):
                return None  # "72.4 #6〜8": a range, not a label
        m = _EXERCISE_PART.match(text, start)
        if m:
            if kind is None and not has_exercise:
                has_exercise, unit, base_end = True, int(m.group("unit")), m.end()
            pos, prev = m.end(), "exercise"
            continue
        m = _UNIT.match(text, start)
        if m and kind is None and not has_exercise and unit is None:
            unit, pos, prev = int(m.group(0)), m.end(), "unit"
            continue
        m = _KIND.match(text, start)
        if m:
            if kind is None:
                kind, base_end = KIND_WORDS[m.group(0)], m.end()
            pos, prev = m.end(), "page" if m.group(0) in ("左ページ", "右ページ") else "kind"
            continue
        if prev == "page":
            m = _LETTER.match(text, start)
            if m:
                pos, prev = m.end(), "letter"
                continue
        if kind is not None:
            m = _QUALIFIER.match(text, start)
            if m:
                pos, prev = m.end(), "qualifier"
                continue
        break

    if pos == 0:
        return None
    anchored = month_day is not None or unit is not None
    if not (kind or has_exercise) or not anchored:
        # "130", "10/9", "Speak", "1分タスク": only before "："
        if not _COLON.match(text, pos):
            return None
    if kind is None:
        kind = "exercise" if has_exercise else "any"
    raw = text[:pos]
    base = raw[:base_end] if base_end is not None and base_end < pos else None
    label = Label(raw=raw, kind=kind, unit=unit, month_day=month_day, base=base)
    return label, _rest(text, pos)


def match_answer_label(
    text: str, group: Label | None, prefix: str | None = None
) -> tuple[Label, str, bool] | None:
    """Read the label of one answer. ``group`` is left by the answer before it.

    Returns (label, answer, written), where ``written`` is False when the answer has
    no label of its own and takes ``group``. Returns None if there is no label and no
    group.

    - "60.2 #5 on paying": its own label.
    - "#6 …" after "60.2 #5": item of the group, "60.2 #6".
    - "英作文 (A)：…" after "10/24 混合 (6)": "10/24 混合 英作文 (A)".
    - "on cooking" after "60.2 #5": no label; the group "60.2".

    ``prefix`` is the ``item_prefix`` of the answer before it: "#5" after
    "10/21 言い直し 141.4 #3" is "10/21 言い直し 141.4 #5".
    """
    if prefix and _ITEM_ONLY.match(text):
        matched = match_label(f"{prefix} {text}")
        if matched is not None:
            return matched[0], matched[1], True
    matched = match_label(text)
    if matched is not None:
        label = matched[0]
        undated = label.month_day is None and label.unit is None
        if not (group and group.month_day and undated and label.kind == "composition"):
            return label, matched[1], True
        # "英作文 (A)：…" after "10/24 混合 (6)" is an item of the group (DESIGN.md 4.2)
    if group is None:
        return None
    if group.kind == "exercise" and not _ITEM_ONLY.match(text):
        return group, text.strip(), False
    combined = match_label(f"{group.raw} {text}")
    if combined is not None and combined[0].key != group.key:
        return combined[0], combined[1], True
    return group, text.strip(), False


def _match_entry_label(text: str, prefix: str | None) -> tuple[Label, str] | None:
    """An entry label; an item number alone ("#6") is added to ``prefix``."""
    matched = match_label(text)
    if matched is None and prefix and _ITEM_ONLY.match(text):
        matched = match_label(f"{prefix} {text}")
    return matched


def match_entry_labels(text: str, prefix: str | None) -> tuple[list[Label], str] | None:
    """Like ``match_answer_label``, but items joined with "・" ("70.4 #3・#5") give
    one label per item.
    """
    m = _JOINED.match(text)
    if m:
        ex = m.group("ex") or prefix
        if ex:
            labels = []
            for item in m.group("items").split("・"):
                matched = match_label(f"{ex} {item}")
                if matched is None:
                    break
                labels.append(matched[0])
            else:
                return labels, _rest(text, m.end())
    matched = _match_entry_label(text, prefix)
    if matched is None:
        return None
    return [matched[0]], matched[1]


def starts_with_label(text: str) -> bool:
    """True if ``text`` starts with a label, an item number alone, or joined items."""
    return bool(match_label(text) or _ITEM_ONLY.match(text) or _JOINED.match(text))


def _rest(text: str, end: int) -> str:
    m = _AFTER_LABEL.match(text, end)
    return text[m.end() :] if m else text[end:]


def resolve_date(month_day: tuple[int, int], reference: date) -> date | None:
    """Turn a month/day label into a full date.

    Labels have no year. The catalog's ``created`` date is the reference: a date
    more than 60 days before it is taken to be in the following year
    (for example, created 2026-09-18 and label 1/5 -> 2027-01-05).
    Returns ``None`` for impossible dates such as 2/30.
    """
    month, day = month_day
    try:
        candidate = date(reference.year, month, day)
    except ValueError:
        return None
    if candidate < reference - timedelta(days=60):
        try:
            candidate = date(reference.year + 1, month, day)
        except ValueError:
            return None
    return candidate
