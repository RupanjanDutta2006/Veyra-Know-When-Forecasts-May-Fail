from backend.app.builder2.location_service import LocationRegistry
from ingestion.historical_gefs_collector import _member_code

def test_registry_has_25_indian_locations():
    locations = LocationRegistry().get_all_location_ids()
    assert len(locations) >= 25
    assert {"dehradun", "shimla", "leh", "visakhapatnam", "thiruvananthapuram"}.issubset(locations)

def test_member_codes_are_unambiguous():
    assert [_member_code(i) for i in range(5)] == ["c00", "p01", "p02", "p03", "p04"]


def test_collector_normalizes_timezone():
    from ingestion import historical_gefs_collector as mod

    issue = mod._utc_date("2017-03-14T00:00:00Z")
    assert issue.tzinfo is not None
    assert str(issue.tzinfo) == "UTC"
    
    # Test naive timestamp conversion
    issue_naive = mod._utc_date("2017-03-14 00:00:00")
    assert issue_naive.tzinfo is not None
    assert str(issue_naive.tzinfo) == "UTC"
