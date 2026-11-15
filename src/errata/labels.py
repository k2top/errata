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

# Dated sources: keyword after "M/D" -> kind.
DATED_KINDS: dict[str, str] = {
    "Speak": "speak",
    "混合": "mixed-test",
    "1分タスク": "daily-task",
}

_EXERCISE = re.compile(
    r"(?P<base>(?P<unit>\d{1,3})\.\d{1,2})(?: (?P<item>#?\d{1,3}[a-z]?))?(?=[\s：:]|$)"
)
# An item number alone, e.g. "#6" or "3a", written after "／" to reuse the exercise before it.
_ITEM_ONLY = re.compile(r"(?:#\d{1,3}[a-z]?|\d{1,3}[a-z])(?=[\s：:]|$)")
# Items joined with "・", e.g. "70.4 #3・#5": one mistake line for several items.
# The exercise part is optional when it can be taken from earlier on the line.
_JOINED = re.compile(
    r"(?:(?P<ex>\d{1,3}\.\d{1,2}) )?"
    r"(?P<items>#?\d{1,3}[a-z]?(?:・#?\d{1,3}[a-z]?)+)(?=[\s：:]|$)"
)
_EXAMPLE = re.compile(r"(?P<unit>\d{1,3}) (?:左|右)ページ [A-Z] の例文")
_DATED = re.compile(
    r"(?P<base>(?P<m>\d{1,2})/(?P<d>\d{1,2}) "
    r"(?P<kw>" + "|".join(re.escape(k) for k in DATED_KINDS) + r"))"
    # Optional qualifiers written in Japanese (no ASCII letters), e.g. 英作文, レベル測定
    r"(?P<qual>(?: [^\sA-Za-z0-9()（）：:]+)*)"
    # Optional item number in half-width parentheses, e.g. (4), (A); the space is optional
    r"(?: ?\((?P<n>[^)\s]+)\))?"
    r"(?=[\s：:]|$)"
)

# Separators allowed between a label and the text that follows it.
_AFTER_LABEL = re.compile(r"\s*[：:]?\s*")


@dataclass(frozen=True)
class Label:
    raw: str
    kind: str  # exercise | example | speak | mixed-test | daily-task | unknown
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
            return self.key == other.key
        return (
            self.kind == other.kind
            and (self.month_day is None or self.month_day == other.month_day)
            and (self.unit is None or self.unit == other.unit)
            and (self.exercise is None or self.exercise == other.exercise)
            and (self.kind not in ("example", "unknown") or self.key == other.key)
        )


UNKNOWN = Label(raw="", kind="unknown")


def match_label(text: str) -> tuple[Label, str] | None:
    """Match a label at the start of ``text``.

    Returns the label and the remaining text (with a ``：`` separator removed),
    or ``None`` if no known label pattern matches.
    """
    m = _EXERCISE.match(text)
    if m:
        label = Label(
            raw=m.group(0),
            kind="exercise",
            unit=int(m.group("unit")),
            base=m.group("base") if m.group("item") else None,
        )
        return label, _rest(text, m.end())

    m = _EXAMPLE.match(text)
    if m:
        label = Label(raw=m.group(0), kind="example", unit=int(m.group("unit")))
        return label, _rest(text, m.end())

    m = _DATED.match(text)
    if m:
        label = Label(
            raw=m.group(0),
            kind=DATED_KINDS[m.group("kw")],
            month_day=(int(m.group("m")), int(m.group("d"))),
            base=m.group("base") if m.group(0) != m.group("base") else None,
        )
        return label, _rest(text, m.end())

    return None


def match_answer_label(text: str, group: Label | None) -> tuple[Label, str, bool] | None:
    """Read the label of one answer. ``group`` is left by the answer before it.

    Returns (label, answer, written), where ``written`` is False when the answer has
    no label of its own and takes ``group``. Returns None if there is no label and no
    group.

    - "60.2 #5 on paying": its own label.
    - "#6 …" after "60.2 #5": item of the group, "60.2 #6".
    - "英作文 (A)：…" after "10/24 混合 (6)": "10/24 混合 英作文 (A)".
    - "on cooking" after "60.2 #5": no label; the group "60.2".
    """
    matched = match_label(text)
    if matched is not None:
        return matched[0], matched[1], True
    if group is None:
        return None
    if group.kind == "exercise" and not _ITEM_ONLY.match(text):
        return group, text.strip(), False
    combined = match_label(f"{group.raw} {text}")
    if combined is not None and combined[0].key != group.key:
        return combined[0], combined[1], True
    return group, text.strip(), False


def _match_entry_label(text: str, exercise: str | None) -> tuple[Label, str] | None:
    """An entry label; an item number alone ("#6") is an item of ``exercise``."""
    matched = match_label(text)
    if matched is None and exercise and _ITEM_ONLY.match(text):
        matched = match_label(f"{exercise} {text}")
    return matched


def match_entry_labels(text: str, exercise: str | None) -> tuple[list[Label], str] | None:
    """Like ``match_answer_label``, but items joined with "・" ("70.4 #3・#5") give
    one label per item.
    """
    m = _JOINED.match(text)
    if m:
        ex = m.group("ex") or exercise
        if ex:
            labels = []
            for item in m.group("items").split("・"):
                matched = match_label(f"{ex} {item}")
                if matched is None:
                    break
                labels.append(matched[0])
            else:
                return labels, _rest(text, m.end())
    matched = _match_entry_label(text, exercise)
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
