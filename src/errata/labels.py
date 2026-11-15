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

_EXERCISE = re.compile(r"(?P<unit>\d{1,3})\.(?P<ex>\d{1,2}) (?P<item>#?\d{1,3}[a-z]?)(?=[\s：:]|$)")
# An item number alone, e.g. "#6" or "3a", written after "／" to reuse the exercise before it.
_ITEM_ONLY = re.compile(r"(?:#\d{1,3}[a-z]?|\d{1,3}[a-z])(?=[\s：:]|$)")
_EXAMPLE = re.compile(r"(?P<unit>\d{1,3}) (?:左|右)ページ [A-Z] の例文")
_DATED = re.compile(
    r"(?P<m>\d{1,2})/(?P<d>\d{1,2}) "
    r"(?P<kw>" + "|".join(re.escape(k) for k in DATED_KINDS) + r")"
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

    @property
    def key(self) -> str:
        """Normalized form used to pair an entry with its answer.

        Extra spaces are ignored, and "1分タスク(1)" is the same as "1分タスク (1)".
        """
        return re.sub(r"\s*\(", " (", " ".join(self.raw.split()))

    @property
    def exercise(self) -> str | None:
        """For an exercise label such as "60.2 #5", the exercise part "60.2"."""
        return self.raw.split()[0] if self.kind == "exercise" else None


UNKNOWN = Label(raw="", kind="unknown")


def match_label(text: str) -> tuple[Label, str] | None:
    """Match a label at the start of ``text``.

    Returns the label and the remaining text (with a ``：`` separator removed),
    or ``None`` if no known label pattern matches.
    """
    m = _EXERCISE.match(text)
    if m:
        label = Label(raw=m.group(0), kind="exercise", unit=int(m.group("unit")))
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
        )
        return label, _rest(text, m.end())

    return None


def match_answer_label(text: str, exercise: str | None) -> tuple[Label, str] | None:
    """Like ``match_label``, but an item number alone ("#6", "3a") is read as an item
    of ``exercise``, the exercise written earlier on the same answer line or callout.
    """
    matched = match_label(text)
    if matched is None and exercise and _ITEM_ONLY.match(text):
        matched = match_label(f"{exercise} {text}")
    return matched


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
