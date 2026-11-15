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
