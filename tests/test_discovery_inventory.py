from applicant_zero.scoring import Job
from applicant_zero.storage import (
    deactivate_stale_broad_feed_inventory_records, discovery_inventory_summary, initialise_database,
    list_inventory_employers, mark_company_inventory_jobs_inactive, save_discovery_inventory,
)


def test_inventory_keeps_raw_listings_separate_from_review_queue(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    jobs = [
        Job("one", "Data Analyst", "Example", "Sydney", "Adzuna", "https://one", ""),
        Job("two", "Data Analyst", "Example", "Sydney", "Lever", "https://two", ""),
        Job("three", "IT Support Officer", "Other", "NSW", "Adzuna", "https://three", ""),
    ]
    save_discovery_inventory(database, jobs)
    assert discovery_inventory_summary(database) == {"collected": 3, "canonical": 2, "companies": 2}


def test_inventory_updates_seen_listing_without_creating_another_record(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    job = Job("one", "Data Analyst", "Example", "Sydney", "Adzuna", "https://one", "first")
    save_discovery_inventory(database, [job])
    save_discovery_inventory(database, [Job("one", "Data Analyst", "Example", "Sydney", "Adzuna", "https://one", "updated")])
    assert discovery_inventory_summary(database)["collected"] == 1
    assert database.execute("SELECT description FROM discovery_inventory WHERE external_id = 'one'").fetchone()[0] == "updated"


def test_inventory_groups_employers_across_sources(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    save_discovery_inventory(database, [
        Job("one", "Data Analyst", "Example", "Sydney", "Adzuna", "https://one", ""),
        Job("two", "BI Analyst", "Example", "Sydney", "Lever", "https://two", ""),
    ])
    employer = list_inventory_employers(database)[0]
    assert employer["company"] == "Example"
    assert employer["distinct_listings"] == 2
    assert {"Adzuna", "Lever"}.issubset(set(employer["sources"].split(",")))


def test_successful_board_snapshot_retires_only_that_company_and_source(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    save_discovery_inventory(database, [
        Job("lever-old", "Data Analyst", "Example", "Sydney", "Lever", "https://one", ""),
        Job("adzuna-same-company", "Data Analyst", "Example", "Sydney", "Adzuna", "https://two", ""),
        Job("lever-other-company", "Data Analyst", "Other", "Sydney", "Lever", "https://three", ""),
    ])
    assert mark_company_inventory_jobs_inactive(database, "Example", "Lever", []) == 1
    active = {row[0] for row in database.execute("SELECT external_id FROM discovery_inventory WHERE is_active = 1")}
    assert active == {"adzuna-same-company", "lever-other-company"}


def test_old_broad_feed_inventory_is_retired_without_deleting_it(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    save_discovery_inventory(database, [
        Job("old", "Data Analyst", "Example", "Sydney", "Adzuna", "https://one", ""),
        Job("board", "Data Analyst", "Example", "Sydney", "Lever", "https://two", ""),
    ])
    database.execute("UPDATE discovery_inventory SET last_seen_at = '2000-01-01' WHERE external_id = 'old'")
    database.commit()
    assert deactivate_stale_broad_feed_inventory_records(database) == 1
    assert database.execute("SELECT is_active FROM discovery_inventory WHERE external_id = 'old'").fetchone()[0] == 0
    assert database.execute("SELECT is_active FROM discovery_inventory WHERE external_id = 'board'").fetchone()[0] == 1
