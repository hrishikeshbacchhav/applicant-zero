from applicant_zero.dashboard import build_page


def test_empty_dashboard_has_guidance(tmp_path):
    page = build_page(tmp_path / "missing.sqlite3")
    assert "No jobs collected yet" in page
