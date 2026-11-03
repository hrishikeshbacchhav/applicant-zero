from datetime import date

from applicant_zero.source_schedule import due_today, record_attempt, rotating_board_batch


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


def test_public_board_batches_rotate_fairly_and_persist_the_cursor(tmp_path):
    boards = [{"company": f"Board {number}"} for number in range(5)]

    assert [item["company"] for item in rotating_board_batch(tmp_path, boards, 2)] == ["Board 0", "Board 1"]
    assert [item["company"] for item in rotating_board_batch(tmp_path, boards, 2)] == ["Board 2", "Board 3"]
    assert [item["company"] for item in rotating_board_batch(tmp_path, boards, 2)] == ["Board 4", "Board 0"]


def test_public_board_batch_recovers_from_invalid_private_cursor(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    (private / "board_refresh_cursor.json").write_text("not json", encoding="utf-8")

    assert rotating_board_batch(tmp_path, [{"company": "One"}], 1) == [{"company": "One"}]
