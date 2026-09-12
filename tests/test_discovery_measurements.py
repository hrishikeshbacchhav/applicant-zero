from applicant_zero.discovery_measurements import canonical_unique_jobs, measure_sources
from applicant_zero.provider_trials import assess_trial_sample
from applicant_zero.scoring import Job
from applicant_zero.sources.adzuna import QueryFetchReport
from applicant_zero.storage import initialise_database, latest_source_measurements, recent_query_measurements, record_query_measurements, record_source_measurements


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


def test_canonical_unique_jobs_does_not_inflate_syndicated_listing_counts():
    jobs = [job("a", "Adzuna"), job("b", "Lever"), job("c", "Lever", title="Support Analyst")]
    unique = canonical_unique_jobs(jobs)
    assert [item.external_id for item in unique] == ["a", "c"]


def test_latest_source_measurements_are_persisted(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    record_source_measurements(database, [{"source": "Adzuna", "collected_count": 3, "relevant_count": 2, "distinct_count": 2, "repeated_count": 1, "request_count": 2}])
    assert latest_source_measurements(database)[0]["relevant_count"] == 2


def test_query_measurements_keep_returned_and_relevant_counts_distinct(tmp_path):
    database = initialise_database(tmp_path / "jobs.sqlite3")
    report = QueryFetchReport("data analyst", "Sydney", 2, 51, external_ids=("a", "b"))
    record_query_measurements(database, [report], {"a"})
    row = recent_query_measurements(database)[0]
    assert row["returned_count"] == 51
    assert row["relevant_count"] == 1


def test_provider_trial_assessment_reports_existing_overlap():
    report = assess_trial_sample([job("a", "Trial"), job("b", "Trial", title="Support Analyst")], [{"title": "Analyst", "company": "Example", "location": "Sydney"}])
    assert report["received"] == 2
    assert report["overlaps_current_database"] == 1
    assert report["new_to_current_database"] == 1
