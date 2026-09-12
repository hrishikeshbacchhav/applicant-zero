from applicant_zero.inventory_rescoring import rescore_active_inventory
from applicant_zero.scoring import Job
from applicant_zero.storage import get_match, initialise_database, save_discovery_inventory


def test_campaign_change_rescores_existing_inventory_without_refetching(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = Job("support", "IT Support Officer", "Example", "Sydney", "Adzuna", "https://example.test", "Technical support and stakeholder communication.")
    save_discovery_inventory(database, [job])

    paused = rescore_active_inventory(database, {"data_bi"})
    assert paused == {"rescored": 1, "relevant": 0}
    assert get_match(database, "support")["recommendation"] == "Skip"

    enabled = rescore_active_inventory(database, {"it_support"})
    assert enabled == {"rescored": 1, "relevant": 1}
    assert get_match(database, "support")["recommendation"] == "Review"
