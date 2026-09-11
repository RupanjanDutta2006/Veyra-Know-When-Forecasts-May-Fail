import pandas as pd
import pytest
from ingestion.historical_gefs_collector import _member_code, _url, HistoricalGEFSCollector


def test_member_code_mapping():
    assert _member_code(0) == 'c00'
    assert _member_code(1) == 'p01'
    assert _member_code(10) == 'p10'


def test_authoritative_url_contains_exact_run_member_and_variable():
    issue = pd.Timestamp('2017-03-14T00:00:00Z')
    url = _url(issue, 0, 'tmp_2m')
    assert url.endswith('/2017/2017031400/c00/Days:1-10/tmp_2m_2017031400_c00.grib2')


def test_reforecast_requires_real_forecast_leads():
    with pytest.raises(ValueError, match='3 and 237'):
        HistoricalGEFSCollector().collect_run('2017-03-14T00:00:00Z', 22.57, 88.36, 'kolkata', horizon_hours=0)


def test_reforecast_rejects_non_00z_before_network():
    with pytest.raises(ValueError, match='00Z'):
        HistoricalGEFSCollector().collect_run(
            '2017-03-14T06:00:00Z', 22.57, 88.36, 'kolkata'
        )
