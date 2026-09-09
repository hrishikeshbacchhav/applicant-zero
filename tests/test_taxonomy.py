from applicant_zero.taxonomy import classify_lane


def test_taxonomy_recognises_related_data_and_support_titles():
    assert classify_lane("Operations Excellence Analyst").identifier == "business_analysis"
    assert classify_lane("Service Desk Analyst").identifier == "it_support"
    assert classify_lane("Workforce Planning Analyst").identifier == "commercial_analytics"
