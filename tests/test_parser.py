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


def test_answer_item_inherits_previous_exercise():
    # "／ #6 …" and "／ 3a …" reuse the exercise number written before them.
    text = HEADER + dedent("""
        ## A 前置詞

        - 60.2 #5 she insisted **to pay** for it
        - 60.2 #6 I'm used **to work** late
        - 64.4 2c he gave up **to try**
        - 64.4 3a I'm afraid **to fall**

        > [!check]- 正答
        > 60.2 #5 on paying ／ #6 to working ／ 64.4 2c trying ／ 3a of falling
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == [
        "on paying",
        "to working",
        "trying",
        "of falling",
    ]


def test_inherited_item_does_not_cross_callouts():
    text = HEADER + dedent("""
        ## A 前置詞

        - 60.2 #5 she insisted **to pay** for it

        > [!check]- 正答
        > 60.2 #5 on paying

        ## B 動詞

        - 60.3 #6 I'm used **to work** late

        > [!check]- 正答
        > #6 to working
        """)
    assert codes(parse_text(text)) == ["no-answer", "unknown-answer-label"]


def test_item_number_without_space_pairs_with_spaced_answer():
    text = HEADER + dedent("""
        ## D 冠詞

        - 11/10 1分タスク(1) very useful **informations**

        > [!check]- 正答
        > 11/10 1分タスク (1)：very useful information
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert catalog.entries[0].answer == "very useful information"


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


# -- slashes inside parentheses and several mistakes on one line ------------------


def test_slash_inside_parentheses_does_not_split_answer():
    text = HEADER + dedent("""
        ## A 前置詞

        - 10/20 Speak I **felt** tired
        - 10/21 Speak she **arrive** late

        > [!check]- 正答
        > 10/20 Speak：I was tired（was／felt）／ 10/21 Speak：she arrived（arrive／arrives）
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == [
        "I was tired（was／felt）",
        "she arrived（arrive／arrives）",
    ]


def test_several_mistakes_on_one_entry_line():
    text = HEADER + dedent("""
        ## A 動詞の形

        - 54.1 #12 stop **to smoke**（やめる）／ #13 enjoy **to swim** ／ 54.3 2b keep **to run**
        - 55.1 #4 We **hardly meet** last year.（a／b どちらも違う）／ #6 he **hardly call** me

        > [!check]- 正答
        > 54.1 #12 smoking ／ #13 swimming ／ 54.3 2b running
        > 55.1 #4 hardly met ／ #6 hardly called
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    entries = catalog.entries
    assert [e.label.raw for e in entries] == [
        "54.1 #12",
        "54.1 #13",
        "54.3 2b",
        "55.1 #4",
        "55.1 #6",
    ]
    assert entries[0].text == "stop to smoke"
    assert entries[0].memo == "やめる"
    assert entries[1].error_parts == ["to swim"]
    assert entries[3].text == "We hardly meet last year."
    assert entries[3].memo == "a／b どちらも違う"
    assert [e.answer for e in entries] == [
        "smoking",
        "swimming",
        "running",
        "hardly met",
        "hardly called",
    ]
    assert all(e.line == entries[0].line for e in entries[:3])


def test_part_without_label_is_another_entry_with_the_same_label():
    text = HEADER + dedent("""
        ## A 動詞の形

        - 10/27 Speak there **was** many people（were）／ we **must not** go（shouldn't have）
        - 57.2 #6 either tea / coffee **are** fine

        > [!check]- 正答
        > 10/27 Speak：were ／ we shouldn't have gone
        > 57.2 #6 is fine
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    first, second, third = catalog.entries
    assert (first.label.raw, first.text, first.memo) == (
        "10/27 Speak",
        "there was many people",
        "were",
    )
    assert (second.label.raw, second.text) == ("10/27 Speak", "we must not go")
    assert [first.answer, second.answer] == ["were", "we shouldn't have gone"]
    assert third.text == "either tea / coffee are fine"


def test_joined_items_share_one_sentence():
    text = HEADER + dedent("""
        ## A 動詞の形

        - 70.4 #3・#5 **two or three day**（複数形）

        > [!check]- 正答
        > 70.4 #3 two or three days ／ #5 two or three days
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.label.raw for e in catalog.entries] == ["70.4 #3", "70.4 #5"]
    assert [e.text for e in catalog.entries] == ["two or three day"] * 2
    assert [e.memo for e in catalog.entries] == ["複数形"] * 2


def test_joined_items_take_one_sentence_each():
    text = HEADER + dedent("""
        ## A 句動詞

        - 141.1 #2・#3 she made up **a plan** ／ he came up with **an excuse**（入れ替わり）

        > [!check]- 正答
        > 141.1 #2 b（came up with）・#3 c（made up）
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    first, second = catalog.entries
    assert (first.label.raw, first.text, first.memo) == ("141.1 #2", "she made up a plan", None)
    assert (second.label.raw, second.text, second.memo) == (
        "141.1 #3",
        "he came up with an excuse",
        "入れ替わり",
    )
    assert [e.answer for e in catalog.entries] == ["b（came up with）", "c（made up）"]


# -- answers with a short label or no label (DESIGN.md 4.1) -----------------------


def test_second_answer_without_label_uses_the_group():
    text = HEADER + dedent("""
        ## A 前置詞

        - 10/20 Speak we **discussed about** it
        - 10/20 Speak I **arrived to** Tokyo

        > [!check]- 正答
        > 10/20 Speak：we discussed it ／ I arrived in Tokyo
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == ["we discussed it", "I arrived in Tokyo"]
    assert [e.answer_by_order for e in catalog.entries] == [False, True]


def test_answer_without_item_number_covers_numbered_entries():
    text = HEADER + dedent("""
        ## D 冠詞

        - 11/10 1分タスク(1) very useful **informations**
        - 11/10 1分タスク(2) two **luggages**

        > [!check]- 正答
        > 11/10 1分タスク：very useful information ／ two pieces of luggage
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == [
        "very useful information",
        "two pieces of luggage",
    ]
    assert all(e.answer_by_order for e in catalog.entries)


def test_exercise_alone_covers_its_items_in_order():
    text = HEADER + dedent("""
        ## F 形容詞

        - 96.3 #4 the film was **bored** ／ #6 I was **boring**

        > [!check]- 正答
        > 96.3：boring ／ bored
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == ["boring", "bored"]


def test_full_labels_are_paired_before_short_ones():
    text = HEADER + dedent("""
        ## A 前置詞

        - 10/24 混合 英作文 (A) the answer **of** the user
        - 10/24 混合 (6) wait **to** me
        - 10/24 混合 (9) listen **me**

        > [!check]- 正答
        > 10/24 混合：wait for me ／ listen to me ／ 英作文 (A)：the user's answer
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == [
        "the user's answer",
        "wait for me",
        "listen to me",
    ]
    assert [e.answer_by_order for e in catalog.entries] == [False, True, True]


def test_group_is_kept_across_answer_lines():
    text = HEADER + dedent("""
        ## B 動詞の形

        - 60.2 #5 insist **to pay** ／ #6 keen **to cook**

        > [!check]- 正答
        > 60.2 #5 on paying
        > on cooking
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert [e.answer for e in catalog.entries] == ["on paying", "on cooking"]


def test_bold_line_in_callout_is_a_note():
    text = HEADER + dedent("""
        ## A 前置詞

        - 60.1 #8 look forward to **meet**

        > [!check]- 正答
        > 60.1 #8 meeting
        > **3件とも to の後ろを原形にしていた。**
        """)
    catalog = parse_text(text)
    assert catalog.issues == []
    assert catalog.entries[0].answer == "meeting"


def test_answer_without_label_or_group_is_reported():
    text = HEADER + dedent("""
        ## A 前置詞

        - 60.1 #8 look forward to **meet**

        > [!check]- 正答
        > meeting
        """)
    catalog = parse_text(text)
    assert "unknown-answer-label" in codes(catalog)


def test_extra_short_answer_is_an_orphan():
    text = HEADER + dedent("""
        ## F 形容詞

        - 96.3 #4 the film was **bored**

        > [!check]- 正答
        > 96.3：boring ／ bored
        """)
    catalog = parse_text(text)
    assert codes(catalog) == ["orphan-answer"]
    assert catalog.entries[0].answer == "boring"


def test_unknown_label_in_answer_does_not_take_the_group():
    text = HEADER + dedent("""
        ## B 動詞の形

        - 60.2 #5 insist **to pay**

        > [!check]- 正答
        > 60.2 #5 on paying
        > 10/9 想起：I moved to Osaka ／ I live there
        > 130：looked for it
        """)
    catalog = parse_text(text)
    assert codes(catalog) == ["unknown-answer-label", "unknown-answer-label"]
    assert catalog.entries[0].answer == "on paying"


def test_bare_number_after_exercise_group_is_not_an_item():
    text = HEADER + dedent("""
        ## B 句動詞

        - 141.4 #3 **made up** it

        > [!check]- 正答
        > 141.4 #3 made it up ／ 142：threw them away
        """)
    catalog = parse_text(text)
    assert codes(catalog) == ["unknown-answer-label"]
