import json

from applicant_zero.ai_drafting import DraftingError, _json_from_text, _load_evidence


def test_json_draft_parser_accepts_json_code_fence():
    assert _json_from_text("```json\n{\"cover_letter\": \"Hello\"}\n```")["cover_letter"] == "Hello"


def test_evidence_library_requires_real_facts(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"truthful_evidence": ["Replace this with a verified fact."]}), encoding="utf-8")
    try:
        _load_evidence(path)
    except DraftingError as error:
        assert "verified evidence" in str(error)
    else:
        raise AssertionError("Expected drafting setup to reject placeholder evidence")
