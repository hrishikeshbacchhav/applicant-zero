import json
from pathlib import Path

from applicant_zero.campaigns import active_lanes, campaign_query_allocation, consume_discovery_query_plan, discovery_query_plan, discovery_query_status, load_campaigns, next_discovery_query_plan, save_enabled_campaigns


ROOT = Path(__file__).resolve().parents[1]


def test_shipped_campaigns_cover_every_candidate_role_group_by_default():
    active = {campaign.identifier for campaign in load_campaigns(ROOT) if campaign.active}

    assert active == {"data_business", "it_support", "broader_it", "administration"}
    payload = json.loads((ROOT / "data" / "search_campaigns.starter.json").read_text(encoding="utf-8"))
    assert payload["max_queries_per_refresh"] == 20
    assert next(campaign for campaign in load_campaigns(ROOT) if campaign.identifier == "administration").full_time_only


def _write_starter(root):
    (root / "data").mkdir()
    (root / "data" / "search_campaigns.starter.json").write_text(json.dumps({
        "locations": ["Sydney", "NSW"], "max_queries_per_refresh": 3,
        "campaigns": [
            {"id": "data", "label": "Data", "role_lanes": ["data_bi"], "queries": ["data analyst", "bi analyst"], "active": True},
            {"id": "admin", "label": "Administration", "role_lanes": ["administration"], "queries": ["administration officer"], "active": False},
        ],
    }), encoding="utf-8")


def test_campaigns_limit_query_budget_and_include_sydney_and_nsw(tmp_path):
    _write_starter(tmp_path)
    assert active_lanes(tmp_path) == {"data_bi"}
    assert discovery_query_plan(tmp_path) == [("data analyst", "Sydney"), ("data analyst", "NSW"), ("bi analyst", "Sydney")]


def test_candidate_can_switch_campaigns_in_private_runtime(tmp_path):
    _write_starter(tmp_path)
    campaigns = save_enabled_campaigns(tmp_path, {"admin"})
    assert [campaign.identifier for campaign in campaigns if campaign.active] == ["admin"]
    assert active_lanes(tmp_path) == {"administration"}
    assert (tmp_path / "private" / "search_campaigns.json").exists()


def test_capped_refresh_shares_queries_across_active_campaigns(tmp_path):
    _write_starter(tmp_path)
    save_enabled_campaigns(tmp_path, {"data", "admin"})

    plan = discovery_query_plan(tmp_path)

    assert plan == [
        ("data analyst", "Sydney"), ("administration officer", "Sydney"),
        ("data analyst", "NSW"),
    ]
    assert campaign_query_allocation(tmp_path) == {"data": 2, "admin": 1}


def test_overlapping_campaign_queries_do_not_consume_broad_feed_capacity_twice(tmp_path):
    _write_starter(tmp_path)
    path = tmp_path / "data" / "search_campaigns.starter.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["max_queries_per_refresh"] = 8
    payload["campaigns"][0]["queries"] = ["Data Analyst", " data   analyst "]
    payload["campaigns"][1]["active"] = True
    payload["campaigns"][1]["queries"] = ["data analyst", "Administration Officer"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert discovery_query_plan(tmp_path) == [
        ("Data Analyst", "Sydney"), ("Data Analyst", "NSW"),
        ("Administration Officer", "Sydney"), ("Administration Officer", "NSW"),
    ]
    assert campaign_query_allocation(tmp_path) == {"data": 2, "admin": 2}


def test_empty_campaign_selection_produces_no_broad_feed_queries(tmp_path):
    _write_starter(tmp_path)
    save_enabled_campaigns(tmp_path, set())
    assert discovery_query_plan(tmp_path) == []
    assert campaign_query_allocation(tmp_path) == {}


def test_rotation_advances_after_a_bounded_refresh_and_respects_daily_cap(tmp_path):
    _write_starter(tmp_path)
    first = next_discovery_query_plan(tmp_path)
    assert first == [("data analyst", "Sydney"), ("data analyst", "NSW"), ("bi analyst", "Sydney")]
    consume_discovery_query_plan(tmp_path, len(first))
    second = next_discovery_query_plan(tmp_path)
    assert second == [("bi analyst", "NSW"), ("data analyst", "Sydney"), ("data analyst", "NSW")]

    save_enabled_campaigns(tmp_path, {"data"})
    path = tmp_path / "private" / "search_campaigns.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["max_queries_per_day"] = 3
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert discovery_query_status(tmp_path)["remaining_today"] == 0
    assert next_discovery_query_plan(tmp_path) == []


def test_monthly_cap_limits_queries_even_when_daily_allowance_remains(tmp_path):
    _write_starter(tmp_path)
    path = tmp_path / "data" / "search_campaigns.starter.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["max_api_calls_per_day"] = 10
    payload["max_api_calls_per_month"] = 4
    path.write_text(json.dumps(payload), encoding="utf-8")

    consume_discovery_query_plan(tmp_path, attempted_queries=3, api_calls=3)
    status = discovery_query_status(tmp_path)
    assert status["remaining_today"] == 1
    assert status["monthly_remaining"] == 1
    assert status["planned_api_calls"] == 1

    consume_discovery_query_plan(tmp_path, attempted_queries=1, api_calls=1)
    status = discovery_query_status(tmp_path)
    assert status["calls_this_month"] == 4
    assert next_discovery_query_plan(tmp_path) == []


def test_private_campaign_switches_inherit_new_shipped_provider_constraints(tmp_path):
    _write_starter(tmp_path)
    starter = json.loads((tmp_path / "data" / "search_campaigns.starter.json").read_text(encoding="utf-8"))
    starter["campaigns"][1]["full_time_only"] = True
    (tmp_path / "data" / "search_campaigns.starter.json").write_text(json.dumps(starter), encoding="utf-8")
    save_enabled_campaigns(tmp_path, {"admin"})
    private = json.loads((tmp_path / "private" / "search_campaigns.json").read_text(encoding="utf-8"))
    for campaign in private["campaigns"]:
        campaign.pop("full_time_only", None)
    (tmp_path / "private" / "search_campaigns.json").write_text(json.dumps(private), encoding="utf-8")
    assert next(campaign for campaign in load_campaigns(tmp_path) if campaign.identifier == "admin").full_time_only


def test_private_campaigns_inherit_new_shipped_role_terms_without_changing_switches(tmp_path):
    _write_starter(tmp_path)
    save_enabled_campaigns(tmp_path, {"admin"})
    starter_path = tmp_path / "data" / "search_campaigns.starter.json"
    starter = json.loads(starter_path.read_text(encoding="utf-8"))
    starter["campaigns"][1]["queries"].append("records officer")
    starter["campaigns"][1]["role_lanes"].append("data_operations")
    starter_path.write_text(json.dumps(starter), encoding="utf-8")

    campaigns = {campaign.identifier: campaign for campaign in load_campaigns(tmp_path)}

    assert campaigns["admin"].active
    assert not campaigns["data"].active
    assert "records officer" in campaigns["admin"].queries
    assert "data_operations" in campaigns["admin"].role_lanes
