import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_research_boards.py"
SPEC = importlib.util.spec_from_file_location("extract_research_boards", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_research_board_extractor_keeps_only_explicit_supported_public_ats_urls():
    rows = [
        ["Employer", "Careers or evidence URL"],
        ["Example", "https://jobs.lever.co/example?location=Sydney"],
        ["Unsupported", "https://example.test/careers"],
        ["Another", "https://boards.greenhouse.io/another/jobs/123"],
    ]
    boards = MODULE.research_public_boards(rows)
    assert [(item["company"], item["ats"], item["token"]) for item in boards] == [
        ("Example", "lever", "example"), ("Another", "greenhouse", "another"),
    ]
