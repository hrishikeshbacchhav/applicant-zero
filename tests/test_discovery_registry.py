import json
from pathlib import Path

from applicant_zero.discovery_registry import board_coverage, discovery_overview, employer_coverage_rows, load_sources, load_targets


ROOT = Path(__file__).resolve().parents[1]


def test_source_register_has_public_and_manual_routes():
    sources = load_sources(ROOT / "data" / "discovery_sources.starter.json")
    assert {source.identifier for source in sources} >= {"lever", "greenhouse", "ashby", "seek", "linkedin"}
    assert any(source.mode == "public_ats_api" for source in sources)


def test_target_universe_is_deduplicated_and_prioritised():
    targets = load_targets(ROOT / "data" / "target_companies.starter.json")
    assert len(targets) >= 75
    assert len({item.company.casefold() for item in targets}) == len(targets)
    assert targets[0].priority == 1
    coverage = board_coverage(targets, ROOT / "data" / "company_boards.starter.json")
    assert "Plenti" in coverage["configured"]
    assert "Canva" in coverage["research_needed"]


def test_discovery_overview_labels_automated_and_manual_coverage():
    overview = discovery_overview(
        ROOT / "data" / "discovery_sources.starter.json",
        ROOT / "data" / "target_companies.starter.json",
        ROOT / "data" / "company_boards.starter.json",
    )
    assert overview["target_count"] >= 80
    assert "Lever career boards" in overview["automated_sources"]
    assert overview["configured_count"] >= 6
    boards = json.loads((ROOT / "data" / "company_boards.starter.json").read_text(encoding="utf-8"))
    assert len(boards) >= 18
    assert {"Omni", "Lime", "Qualtrics"} <= {board["company"] for board in boards}


def test_employer_coverage_map_keeps_priority_sector_and_route():
    rows = employer_coverage_rows(ROOT / "data" / "target_companies.starter.json", ROOT / "data" / "company_boards.starter.json")
    plenti = next(row for row in rows if row["company"] == "Plenti")
    canva = next(row for row in rows if row["company"] == "Canva")
    assert plenti["route"] == "Public ATS refresh"
    assert plenti["ats"] == "Lever"
    assert canva["route"] == "Research queue"
