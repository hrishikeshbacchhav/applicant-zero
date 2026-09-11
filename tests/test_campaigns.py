import json

from applicant_zero.campaigns import active_lanes, campaign_query_allocation, consume_discovery_query_plan, discovery_query_plan, discovery_query_status, load_campaigns, next_discovery_query_plan, save_enabled_campaigns


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
