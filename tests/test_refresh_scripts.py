from pathlib import Path


def test_scheduled_refresh_keeps_gmail_sync_explicit_and_private():
    root = Path(__file__).resolve().parents[1]
    refresh = (root / "scripts" / "refresh_company_boards.ps1").read_text(encoding="utf-8")
    schedule = (root / "scripts" / "create_daily_refresh_task.ps1").read_text(encoding="utf-8")

    assert "[switch]$SyncGmail" in refresh
    assert "private\\gmail_token.json" in refresh
    assert "--gmail-sync" in refresh
    assert "[switch]$SyncGmail" in schedule
    assert "-SyncGmail" in schedule


def test_bulk_public_board_import_script_is_local_and_csv_based():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "import_public_board_urls.py").read_text(encoding="utf-8")
    assert "careers_url" in script
    assert "add_public_board_urls" in script
    assert "csv.DictReader" in script
