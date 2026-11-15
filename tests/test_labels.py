from datetime import date

import pytest

from errata.labels import match_label, resolve_date


@pytest.mark.parametrize(
    ("text", "raw", "kind", "rest"),
    [
        ("60.1 #8 I'm looking forward", "60.1 #8", "exercise", "I'm looking forward"),
        ("64.4 2c was", "64.4 2c", "exercise", "was"),
        ("140.3 #10：answer", "140.3 #10", "exercise", "answer"),
        ("126 左ページ B の例文 She has", "126 左ページ B の例文", "example", "She has"),
        ("10/20 Speak we discussed", "10/20 Speak", "speak", "we discussed"),
        ("10/6 Speak レベル測定 I am", "10/6 Speak レベル測定", "speak", "I am"),
        ("10/3 混合 (4) This is", "10/3 混合 (4)", "mixed-test", "This is"),
        ("10/17 混合 英作文 (A)：I thought", "10/17 混合 英作文 (A)", "mixed-test", "I thought"),
        ("9/18 1分タスク It was", "9/18 1分タスク", "daily-task", "It was"),
        ("11/10 1分タスク (1)：The report", "11/10 1分タスク (1)", "daily-task", "The report"),
        ("11/10 1分タスク(1) The report", "11/10 1分タスク(1)", "daily-task", "The report"),
        ("10/3 混合(4)：This is", "10/3 混合(4)", "mixed-test", "This is"),
    ],
)
def test_known_labels(text, raw, kind, rest):
    label, remainder = match_label(text)
    assert label.raw == raw
    assert label.kind == kind
    assert remainder == rest


def test_unit_and_month_day():
    label, _ = match_label("60.1 #8 x")
    assert label.unit == 60
    label, _ = match_label("11/15 混合 (4) x")
    assert label.month_day == (11, 15)


@pytest.mark.parametrize("text", ["I have went", "Unit 60 test", "10/20 Zoom call"])
def test_unknown_labels(text):
    assert match_label(text) is None


def test_label_key_ignores_extra_spaces():
    a, _ = match_label("10/3 混合 (4) x")
    b, _ = match_label("10/3 混合 (4)：y")
    assert a.key == b.key


def test_label_key_ignores_space_before_item_number():
    a, _ = match_label("11/10 1分タスク(1) x")
    b, _ = match_label("11/10 1分タスク (1)：y")
    assert a.key == b.key == "11/10 1分タスク (1)"


def test_resolve_date_same_year():
    assert resolve_date((11, 15), date(2026, 9, 18)) == date(2026, 11, 15)


def test_resolve_date_next_year():
    assert resolve_date((1, 5), date(2026, 9, 18)) == date(2027, 1, 5)


def test_resolve_date_shortly_before_created_stays_in_same_year():
    # Entries copied from a few days before the catalog was created.
    assert resolve_date((9, 10), date(2026, 9, 18)) == date(2026, 9, 10)


def test_resolve_date_impossible():
    assert resolve_date((2, 30), date(2026, 9, 18)) is None


# -- parts of a label (DESIGN.md 4.2) ----------------------------------------------


@pytest.mark.parametrize(
    ("text", "raw", "kind", "base", "rest"),
    [
        ("10/9 想起：I moved", "10/9 想起", "recall", None, "I moved"),
        ("10/9 前日の想起の例文 I moved", "10/9 前日の想起の例文", "recall", None, "I moved"),
        ("10/13 前日の想起 keep up", "10/13 前日の想起", "recall", None, "keep up"),
        ("11/4 言い直し 100.3 #2 Why", "11/4 言い直し 100.3 #2", "redo", "11/4 言い直し", "Why"),
        (
            "10/10 言い直し 英作文 (B) It",
            "10/10 言い直し 英作文 (B)",
            "redo",
            "10/10 言い直し",
            "It",
        ),
        ("10/31 言い直し (9) I", "10/31 言い直し (9)", "redo", "10/31 言い直し", "I"),
        (
            "10/17 採点後の言い直し 英作文 (A) It",
            "10/17 採点後の言い直し 英作文 (A)",
            "redo",
            "10/17 採点後の言い直し",
            "It",
        ),
        ("9/18夜 1分タスク(1) It", "9/18夜 1分タスク(1)", "daily-task", "9/18夜 1分タスク", "It"),
        ("10/10 英作文 (A) The", "10/10 英作文 (A)", "composition", "10/10 英作文", "The"),
        ("136 左ページの例文 Please", "136 左ページの例文", "example", None, "Please"),
        ("9/28 左ページ例文 I'm", "9/28 左ページ例文", "example", None, "I'm"),
        ("10/16 17 左ページの例文 I", "10/16 17 左ページの例文", "example", None, "I"),
        ("142 左ページ B give", "142 左ページ B", "example", "142 左ページ", "give"),
        ("10/13 Anki（140 のカード） It", "10/13 Anki", "anki", None, "（140 のカード） It"),
        ("10/27 Speak（過去の話）I", "10/27 Speak", "speak", None, "（過去の話）I"),
        ("11/3 言い直し「回答A」", "11/3 言い直し", "redo", None, "「回答A」"),
        (
            "11/10 1分タスク (1)「回答A」",
            "11/10 1分タスク (1)",
            "daily-task",
            "11/10 1分タスク",
            "「回答A」",
        ),
        ("96.3：boring", "96.3", "exercise", None, "boring"),
        ("130：searched", "130", "any", None, "searched"),
        ("10/9：I haven't", "10/9", "any", None, "I haven't"),
        ("Speak：invest", "Speak", "speak", None, "invest"),
        ("1分タスク：the changes", "1分タスク", "daily-task", None, "the changes"),
        ("17 例文：I'm", "17 例文", "example", None, "I'm"),
    ],
)
def test_label_parts(text, raw, kind, base, rest):
    label, remainder = match_label(text)
    assert (label.raw, label.kind, label.base, remainder) == (raw, kind, base, rest)


@pytest.mark.parametrize("text", ["Speak up now", "130 people came", "10/9 I moved", "1分タスク"])
def test_label_without_kind_or_exercise_needs_a_colon(text):
    assert match_label(text) is None


def test_any_kind_covers_by_unit_and_date():
    unit, _ = match_label("130：x")
    date_only, _ = match_label("10/9：x")
    assert unit.covers(match_label("130.2 #3 x")[0])
    assert unit.covers(match_label("130 左ページ B x")[0])
    assert not unit.covers(match_label("131.2 #3 x")[0])
    assert date_only.covers(match_label("10/9 想起 x")[0])
    assert not date_only.covers(match_label("10/10 想起 x")[0])
