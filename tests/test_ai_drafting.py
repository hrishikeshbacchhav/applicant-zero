import json

from applicant_zero.ai_drafting import DEFAULT_DRAFT_MODEL, MAX_DRAFT_OUTPUT_TOKENS, DraftingError, _json_from_text, _load_evidence, _response_text, _usage_summary, check_tailoring_setup, create_question_draft, evidence_for_job


def test_json_draft_parser_accepts_json_code_fence():
    assert _json_from_text("```json\n{\"cover_letter\": \"Hello\"}\n```")["cover_letter"] == "Hello"


def test_response_text_reads_responses_api_message_content():
    response = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "{\"cover_letter\": \"Hello\"}"}]}]}
    assert _response_text(response) == '{"cover_letter": "Hello"}'


def test_drafting_has_a_cost_conscious_default_and_keeps_usage_counts():
    assert DEFAULT_DRAFT_MODEL == "gpt-5.6-terra"
    assert MAX_DRAFT_OUTPUT_TOKENS == 1_200
    assert _usage_summary({"usage": {"input_tokens": 400, "output_tokens": 200, "total_tokens": 600}}) == {"input_tokens": 400, "output_tokens": 200, "total_tokens": 600}


def test_personal_eligibility_questions_are_not_sent_to_the_drafting_service(tmp_path):
    try:
        create_question_draft(tmp_path / "jobs.sqlite3", "job-1", "Do you have unrestricted work rights in Australia?")
    except DraftingError as error:
        assert "Answer this personal eligibility" in str(error)
    else:
        raise AssertionError("Expected personal eligibility question to be held for the candidate")


def test_evidence_library_requires_real_facts(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"truthful_evidence": ["Replace this with a verified fact."]}), encoding="utf-8")
    try:
        _load_evidence(path)
    except DraftingError as error:
        assert "verified evidence" in str(error)
    else:
        raise AssertionError("Expected drafting setup to reject placeholder evidence")


def test_evidence_library_can_add_only_the_relevant_role_lane_facts():
    evidence = {
        "truthful_evidence": ["Built verified SQL reporting."],
        "evidence_by_lane": {
            "data_bi": ["Built verified Power BI dashboards."],
            "it_support": ["Resolved verified support incidents."],
        },
    }
    assert evidence_for_job(evidence, "data_bi") == ["Built verified SQL reporting.", "Built verified Power BI dashboards."]


def test_tailoring_check_reports_missing_private_setup(tmp_path):
    issues = check_tailoring_setup(tmp_path)
    assert "Private candidate profile is not ready." in issues
    assert any("evidence library" in issue for issue in issues)
