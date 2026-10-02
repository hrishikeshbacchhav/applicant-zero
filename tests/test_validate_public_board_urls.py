import importlib.util
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_public_board_urls.py"
SPEC = importlib.util.spec_from_file_location("validate_public_board_urls", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_validator_keeps_readable_explicit_public_boards_and_rejects_others():
    rows = [
        {"company": "Example", "careers_url": "https://jobs.lever.co/example"},
        {"company": "Broken", "careers_url": "https://example.test/jobs"},
        {"company": "Empty but live", "careers_url": "https://boards.greenhouse.io/empty"},
    ]
    with patch.object(MODULE, "fetch_public_board", side_effect=[[{"role": "one"}], []]):
        accepted, rejected = MODULE.validate_rows(rows)
    assert [(row["company"], row["ats"], row["listing_count"]) for row in accepted] == [
        ("Example", "lever", "1"), ("Empty but live", "greenhouse", "0"),
    ]
    assert len(rejected) == 1
    assert "Broken" in rejected[0]


def test_validator_deduplicates_and_applies_a_bounded_input_limit():
    rows = [
        {"company": "First", "careers_url": "https://jobs.lever.co/one"},
        {"company": "Duplicate", "careers_url": "https://jobs.lever.co/one"},
        {"company": "Second", "careers_url": "https://jobs.lever.co/two"},
    ]
    with patch.object(MODULE, "fetch_public_board", return_value=[] ) as fetch:
        accepted, rejected = MODULE.validate_rows(rows, limit=1)
    assert [row["company"] for row in accepted] == ["First"]
    assert rejected == []
    assert fetch.call_count == 1
