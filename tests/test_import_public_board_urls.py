import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_public_board_urls.py"
SPEC = importlib.util.spec_from_file_location("import_public_board_urls", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_board_importer_reads_the_research_extractors_json_output(tmp_path):
    source = tmp_path / "candidate_boards.json"
    source.write_text(json.dumps([
        {"company": "Example", "careers_url": "https://jobs.lever.co/example", "ats": "lever", "token": "example"},
    ]), encoding="utf-8")
    assert MODULE.load_rows(source) == [
        {"company": "Example", "careers_url": "https://jobs.lever.co/example", "ats": "lever", "token": "example"},
    ]
    created, existing, rejected = MODULE.import_rows(
        tmp_path / "private", tmp_path / "starter.json", MODULE.load_rows(source)
    )
    assert (created, existing, rejected) == (1, 0, [])


def test_board_importer_rejects_json_without_a_public_board_url(tmp_path):
    source = tmp_path / "candidate_boards.json"
    source.write_text(json.dumps([{"company": "Example"}]), encoding="utf-8")
    try:
        MODULE.load_rows(source)
    except ValueError as error:
        assert "careers_url" in str(error)
    else:
        raise AssertionError("Expected missing careers URL to be rejected")
