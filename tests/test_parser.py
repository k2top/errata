from datetime import date
from pathlib import Path
from textwrap import dedent

from errata.parser import parse_file, parse_text

EXAMPLE = Path(__file__).parent.parent / "examples" / "vault" / "06-誤答カタログ.md"

HEADER = "---\ntype: error-catalog\ncreated: 2026-09-18\n---\n"


def codes(catalog):
    return [i.code for i in catalog.issues]


# -- the example vault --------------------------------------------------------


def test_example_parses_without_issues():
    catalog = parse_file(EXAMPLE)
    assert catalog.issues == []
    assert catalog.created == date(2026, 9, 18)
    assert list(catalog.categories) == ["A", "D", "F"]
    assert len(catalog.entries) == 9


def test_example_entry_details():
    catalog = parse_file(EXAMPLE)
    a = catalog.categories["A"]
    assert a.title == "動詞ごとの前置詞"
    assert a.rule.startswith("動詞のあとの前置詞")

    first, second, third = a.entries
    assert first.label.raw == "60.1 #8"
    assert first.text == "I'm looking forward to meet the new team"
    assert first.error_parts == ["meet"]
    assert first.answer == "meeting"
    assert first.date is None  # workbook labels have no date

    assert second.error_parts == ["discussed about"]
    assert second.answer == "we discussed the schedule"
    assert second.date == date(2026, 10, 20)

    assert third.memo == "人にとって＝for・5回目・同じ向き"
    assert third.repeat == 5
    assert third.text == "This manual is too hard to me."


def test_multiple_answers_on_one_line():
    catalog = parse_file(EXAMPLE)
    f = catalog.categories["F"]
    assert [e.answer for e in f.entries] == ["was", "could", "I thought it would rain."]


def test_pending_section_has_no_category_and_no_warning():
    catalog = parse_file(EXAMPLE)
    (entry,) = catalog.pending
    assert entry.category_id is None
    assert entry.answer is None


def test_summary_table_rows():
    catalog = parse_file(EXAMPLE)
    assert [(r.category_id, r.count) for r in catalog.summary] == [("A", 3), ("D", 2), ("F", 3)]


def test_entry_id_is_stable_and_unique():
    ids = [e.entry_id for e in parse_file(EXAMPLE).entries]
    assert len(set(ids)) == len(ids)
    assert ids == [e.entry_id for e in parse_file(EXAMPLE).entries]


# -- problems are reported with line numbers -----------------------------------


def test_missing_answer_and_orphan_answer():
    text = HEADER + dedent("""
        ## A 前置詞

        - 60.1 #8 I'm looking forward to **meet** you
        - 60.1 #9 I **insist to** pay

        > [!check]- 正答
        > 60.1 #8 meeting
        > 60.1 #10 on paying
        """)
    catalog = parse_text(text)
    assert codes(catalog) == ["no-answer", "orphan-answer"]
    no_answer = catalog.issues[0]
    assert no_answer.line == 9  # the 60.1 #9 entry


def test_unknown_label_is_kept_as_entry():
    text = HEADER + "\n## A 前置詞\n\n- Zoom call we **discussed about** it\n"
    catalog = parse_text(text)
    (entry,) = catalog.categories["A"].entries
    assert entry.label.kind == "unknown"
    assert "unknown-label" in codes(catalog)


def test_missing_bold_is_a_warning():
    text = HEADER + "\n## A 前置詞\n\n- 60.1 #8 no bold here\n\n> [!check]- 正答\n> 60.1 #8 x\n"
    assert codes(parse_text(text)) == ["no-bold"]


def test_summary_count_mismatch():
    text = HEADER + dedent("""
        ## 件数の一覧（テスト）

        | 分類 | 件数 | 初出 → 最新 | 状態 |
        |---|---|---|---|
        | A 前置詞 | 2 | 60 → 60 | **メモ** |

        ## A 前置詞

        - 60.1 #8 I'm looking forward to **meet** you

        > [!check]- 正答
        > 60.1 #8 meeting
        """)
    catalog = parse_text(text)
    assert codes(catalog) == ["summary-count-mismatch"]


def test_section_not_in_summary_and_summary_without_section():
    text = HEADER + dedent("""
        ## 件数の一覧

        | 分類 | 件数 |
        |---|---|
        | B 冠詞 | 1 |

        ## A 前置詞

        - 60.1 #8 to **meet**

        > [!check]- 正答
        > 60.1 #8 meeting
        """)
    assert sorted(codes(parse_text(text))) == ["section-not-in-summary", "summary-missing-section"]


def test_no_front_matter_means_no_dates():
    catalog = parse_text("## A 前置詞\n\n- 10/20 Speak **discussed about**\n")
    assert catalog.entries[0].date is None
    assert "no-front-matter" in codes(catalog)


def test_duplicate_category_is_an_error():
    text = HEADER + "\n## A one\n\n## A two\n"
    catalog = parse_text(text)
    assert catalog.has_errors
    assert "duplicate-category" in codes(catalog)


def test_same_label_twice_pairs_answers_in_order():
    text = HEADER + dedent("""
        ## A 前置詞

        - 10/20 Speak we **discussed about** it
        - 10/20 Speak I **arrived to** Tokyo

        > [!check]- 正答
        > 10/20 Speak：we discussed it ／ 10/20 Speak：I arrived in Tokyo
        """)
    catalog = parse_text(text)
    assert [e.answer for e in catalog.entries] == ["we discussed it", "I arrived in Tokyo"]
    assert catalog.issues == []
