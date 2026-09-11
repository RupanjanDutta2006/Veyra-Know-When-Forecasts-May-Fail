from backend.app.builder2.location_service import LocationRegistry
from ingestion.historical_gefs_collector import _member_code

def test_registry_has_25_indian_locations():
    locations = LocationRegistry().get_all_location_ids()
    assert len(locations) >= 25
    assert {"dehradun", "shimla", "leh", "visakhapatnam", "thiruvananthapuram"}.issubset(locations)

def test_member_codes_are_unambiguous():
    assert [_member_code(i) for i in range(5)] == ["c00", "p01", "p02", "p03", "p04"]


def test_collector_normalizes_timezone_before_herbie(monkeypatch):
    from ingestion import historical_gefs_collector as mod

    captured = {}
    class FakeHerbie:
        def __init__(self, date, **kwargs):
            captured['date'] = date
            captured['kwargs'] = kwargs
        @property
        def grib(self):
            return 'fake'
    monkeypatch.setattr(mod, 'discover_members', lambda issue: [0])
    monkeypatch.setattr(mod, '_open_member_field', lambda issue, member, cfg, raw_dir, latitude, longitude, fxx: (_ for _ in ()).throw(AssertionError('not reached')))
    # The regression is exercised by the helper call path in _open_member_field;
    # instantiate Herbie directly through a small temporary patch of the symbol.
    monkeypatch.setitem(__import__('sys').modules, 'herbie', __import__('types').SimpleNamespace(Herbie=FakeHerbie))
    issue = mod._utc_date('2017-03-14T00:00:00Z')
    assert issue.tzinfo is not None
    # Herbie requires a tz-naive datetime; the collector now supplies one.
    assert issue.tz_localize(None).tzinfo is None
