import json

from applicant_zero.licensed_providers import enabled_licensed_providers, load_licensed_providers


def test_licensed_provider_is_disabled_until_candidate_enables_it(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "licensed_providers.starter.json").write_text(json.dumps({"providers": [{"id": "sample", "label": "Sample", "enabled": False}]}), encoding="utf-8")
    assert load_licensed_providers(tmp_path)[0].identifier == "sample"
    assert enabled_licensed_providers(tmp_path) == ()
