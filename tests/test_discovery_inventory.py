from applicant_zero.scoring import Job
from applicant_zero.storage import discovery_inventory_summary, initialise_database, save_discovery_inventory


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
