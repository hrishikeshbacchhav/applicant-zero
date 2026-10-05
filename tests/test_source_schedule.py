from datetime import date

from applicant_zero.source_schedule import due_today, record_attempt


def test_daily_source_schedule_allows_one_attempt_per_day(tmp_path):
    today = date(2026, 10, 5)
    assert due_today(tmp_path, "Himalayas", today=today)

    record_attempt(tmp_path, "Himalayas", today=today)

    assert not due_today(tmp_path, "himalayas", today=today)
    assert due_today(tmp_path, "himalayas", today=date(2026, 10, 6))


def test_daily_source_schedule_recovers_from_invalid_private_file(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    (private / "source_schedule.json").write_text("not json", encoding="utf-8")

    assert due_today(tmp_path, "himalayas", today=date(2026, 10, 5))
