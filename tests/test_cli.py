import json
from pathlib import Path

from errata.cli import main

EXAMPLE = Path(__file__).parent.parent / "examples" / "vault" / "06-誤答カタログ.md"


def test_scan_example(capsys):
    assert main(["scan", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "9 entries in 3 categories" in out
    assert "No problems found." in out


def test_scan_json(capsys):
    assert main(["scan", "--json", str(EXAMPLE)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [c["id"] for c in data["categories"]] == ["A", "D", "F"]
    assert data["categories"][0]["entries"][0]["answer"] == "meeting"


def test_scan_strict_fails_on_warnings(tmp_path, capsys):
    catalog = tmp_path / "c.md"
    catalog.write_text("## A x\n\n- 60.1 #8 no bold\n", encoding="utf-8")
    assert main(["scan", str(catalog)]) == 0
    assert main(["scan", "--strict", str(catalog)]) == 1


def test_scan_missing_file(tmp_path, capsys):
    assert main(["scan", str(tmp_path / "nope.md")]) == 2
