import json
import pytest
from pathlib import Path

from applicant_zero.discovery_registry import add_public_board, add_public_board_url, board_coverage, board_health_summary, discovery_overview, employer_coverage_rows, load_recruitment_source_targets, load_sources, load_targets, public_board_from_url
from applicant_zero.discovery_priority import prioritise_targets


ROOT = Path(__file__).resolve().parents[1]


def test_source_register_has_public_and_manual_routes():
    sources = load_sources(ROOT / "data" / "discovery_sources.starter.json")
    assert {source.identifier for source in sources} >= {"lever", "greenhouse", "ashby", "seek", "linkedin"}
    assert any(source.mode == "public_ats_api" for source in sources)
    assert all({"data_bi", "it_support", "it_general", "administration"} <= set(source.role_lanes) for source in sources)


def test_recruitee_public_careers_url_is_recognised():
    assert public_board_from_url("https://example.recruitee.com/o/data-analyst") == ("recruitee", "example")


def test_target_universe_is_deduplicated_and_prioritised():
    targets = load_targets(ROOT / "data" / "target_companies.starter.json")
    assert len(targets) >= 1_500
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
    assert overview["target_count"] >= 1_500
    assert overview["sectors"] >= 20
    assert len(overview["recruitment_source_targets"]) == 15
    assert "Lever career boards" in overview["automated_sources"]
    assert overview["configured_count"] >= 6
    boards = json.loads((ROOT / "data" / "company_boards.starter.json").read_text(encoding="utf-8"))
    assert len(boards) >= 18
    assert {"Omni", "Lime", "Qualtrics"} <= {board["company"] for board in boards}


def test_recruitment_provider_targets_are_kept_separate_from_employer_targets():
    providers = load_recruitment_source_targets(ROOT / "data" / "target_companies.starter.json")
    assert "Workforce Australia" in providers
    assert len(providers) == 15


def test_employer_coverage_map_keeps_priority_sector_and_route():
    rows = employer_coverage_rows(ROOT / "data" / "target_companies.starter.json", ROOT / "data" / "company_boards.starter.json")
    plenti = next(row for row in rows if row["company"] == "Plenti")
    canva = next(row for row in rows if row["company"] == "Canva")
    assert plenti["route"] == "Public ATS refresh"
    assert plenti["ats"] == "Lever"
    assert canva["route"] == "Research queue"


def test_employer_coverage_map_includes_latest_private_board_health():
    rows = employer_coverage_rows(
        ROOT / "data" / "target_companies.starter.json",
        ROOT / "data" / "company_boards.starter.json",
        [{"company": "Plenti", "status": "checked"}],
    )
    assert next(row for row in rows if row["company"] == "Plenti")["health"] == "checked"


def test_board_health_summary_distinguishes_recent_stale_and_unavailable_checks(tmp_path):
    boards = tmp_path / "boards.json"
    boards.write_text(json.dumps([
        {"company": "Recent", "ats": "lever", "token": "recent"},
        {"company": "Stale", "ats": "lever", "token": "stale"},
        {"company": "Unavailable", "ats": "lever", "token": "unavailable"},
        {"company": "Never", "ats": "lever", "token": "never"},
    ]), encoding="utf-8")
    summary = board_health_summary(boards, [
        {"company": "Recent", "status": "checked", "checked_at": "2099-01-01 00:00:00"},
        {"company": "Stale", "status": "checked", "checked_at": "2000-01-01 00:00:00"},
        {"company": "Unavailable", "status": "unavailable", "checked_at": "2099-01-01 00:00:00"},
    ])
    assert summary == {"configured": 4, "checked": 1, "unavailable": 1, "stale": 1, "never_checked": 1}


def test_candidate_can_add_verified_public_board_without_hiding_starters(tmp_path):
    starter = tmp_path / "starter.json"
    starter.write_text(json.dumps([{"company": "Starter", "ats": "lever", "token": "starter-board"}]), encoding="utf-8")
    state = tmp_path / "state"

    entry, created = add_public_board(state, starter, "Example Australia", "greenhouse", "example-australia")

    assert created is True
    assert entry == {"company": "Example Australia", "ats": "greenhouse", "token": "example-australia"}
    saved = json.loads((state / "data" / "company_boards.json").read_text(encoding="utf-8"))
    assert {row["company"] for row in saved} == {"Starter", "Example Australia"}

    duplicate, created = add_public_board(state, starter, "Different label", "greenhouse", "example-australia")
    assert created is False
    assert duplicate["company"] == "Example Australia"


def test_candidate_cannot_add_an_unknown_or_malformed_public_board(tmp_path):
    starter = tmp_path / "starter.json"
    starter.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Choose Greenhouse"):
        add_public_board(tmp_path / "state", starter, "Example", "unknown", "example")
    with pytest.raises(ValueError, match="public board token"):
        add_public_board(tmp_path / "state", starter, "Example", "lever", "bad token")


def test_priority_engine_prefers_healthy_configured_priority_employers():
    targets = load_targets(ROOT / "data" / "target_companies.starter.json")[:2]
    rows = [
        {"company": targets[0].company, "route": "Research queue", "health": "not applicable"},
        {"company": targets[1].company, "route": "Public ATS refresh", "health": "checked"},
    ]
    ranked = prioritise_targets(targets, rows)
    assert ranked[0].company == targets[1].company
    assert "Automatic refresh" in ranked[0].action


def test_supported_public_careers_urls_produce_an_ats_and_board_token(tmp_path):
    assert public_board_from_url("https://jobs.lever.co/example-australia") == ("lever", "example-australia")
    assert public_board_from_url("https://boards.greenhouse.io/example/jobs/7") == ("greenhouse", "example")
    assert public_board_from_url("https://jobs.ashbyhq.com/example") == ("ashby", "example")
    assert public_board_from_url("https://jobs.smartrecruiters.com/Example") == ("smartrecruiters", "Example")
    with pytest.raises(ValueError, match="supported public"):
        public_board_from_url("https://example.com/careers")


def test_candidate_can_save_a_public_board_from_its_url(tmp_path):
    starter = tmp_path / "starter.json"
    starter.write_text("[]", encoding="utf-8")
    entry, created = add_public_board_url(tmp_path / "state", starter, "Example", "https://jobs.lever.co/example")
    assert created is True
    assert entry == {"company": "Example", "ats": "lever", "token": "example"}
