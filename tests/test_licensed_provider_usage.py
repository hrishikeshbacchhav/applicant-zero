import json

from applicant_zero.licensed_providers import LicensedProvider, provider_remaining_today, record_provider_requests


def test_provider_usage_has_a_local_daily_budget(tmp_path):
    provider = LicensedProvider("sample", "Sample", True, 5, 7)
    assert provider_remaining_today(tmp_path, provider) == 7
    record_provider_requests(tmp_path, provider, 3)
    assert provider_remaining_today(tmp_path, provider) == 4
    usage = json.loads((tmp_path / "private" / "licensed_provider_usage.json").read_text(encoding="utf-8"))
    assert usage["sample"]["requests"] == 3
