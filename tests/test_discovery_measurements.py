from applicant_zero.discovery_measurements import measure_sources
from applicant_zero.provider_trials import assess_trial_sample
from applicant_zero.scoring import Job
from applicant_zero.storage import initialise_database, latest_source_measurements, record_source_measurements


def job(identifier, source, company="Example", title="Analyst", location="Sydney"):
    return Job(identifier, title, company, location, source, "https://example.test", "")


def test_source_measurement_keeps_cross_source_repeats_visible():
    rows = measure_sources(
        [job("a", "Adzuna"), job("b", "Lever"), job("c", "Lever", title="Support Analyst")],
        {"a", "c"}, request_counts={"Adzuna": 2}, failure_counts={"Lever": 1},
    )
    adzuna = next(row for row in rows if row["source"] == "Adzuna")
    lever = next(row for row in rows if row["source"] == "Lever")
    assert adzuna["repeated_count"] == 1
    assert lever["distinct_count"] == 1
    assert lever["failure_count"] == 1


def test_latest_source_measurements_are_persisted(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    record_source_measurements(database, [{"source": "Adzuna", "collected_count": 3, "relevant_count": 2, "distinct_count": 2, "repeated_count": 1, "request_count": 2}])
    assert latest_source_measurements(database)[0]["relevant_count"] == 2


def test_provider_trial_assessment_reports_existing_overlap():
    report = assess_trial_sample([job("a", "Trial"), job("b", "Trial", title="Support Analyst")], [{"title": "Analyst", "company": "Example", "location": "Sydney"}])
    assert report["received"] == 2
    assert report["overlaps_current_database"] == 1
    assert report["new_to_current_database"] == 1
