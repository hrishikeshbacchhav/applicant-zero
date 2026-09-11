from applicant_zero.taxonomy import classify_lane


def test_taxonomy_recognises_related_data_and_support_titles():
    assert classify_lane("Operations Excellence Analyst").identifier == "business_analysis"
    assert classify_lane("Service Desk Analyst").identifier == "it_support"
    assert classify_lane("Workforce Planning Analyst").identifier == "commercial_analytics"


def test_title_route_wins_over_an_incidental_description_keyword():
    assert classify_lane("IT Service Desk Analyst", "Build Power BI reports when requested").identifier == "it_support"


def test_taxonomy_recognises_bi_developer_and_technology_ba_routes():
    assert classify_lane("Business Intelligence Developer").identifier == "data_bi"
    assert classify_lane("Technology Business Analyst").identifier == "business_analysis"


def test_source_contracts_include_every_supported_public_board_provider():
    from applicant_zero.taxonomy import SOURCE_CONTRACTS
    identifiers = {item.identifier for item in SOURCE_CONTRACTS}
    assert {"greenhouse", "lever", "ashby", "smartrecruiters", "workable"} <= identifiers
