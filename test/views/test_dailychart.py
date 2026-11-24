import json
from datetime import datetime, timedelta, timezone

import pytest

from puppetboard import app
from puppetboard.views import dailychart
from test import MockDbQuery


def test_json_daily_reports_chart_ok(client, mocker,
                                     mock_puppetdb_environments,
                                     mock_puppetdb_default_nodes):
    query_data = {
        'reports': [
            [{'status': 'changed', 'count': 1}]
            for i in range(app.app.config['DAILY_REPORTS_CHART_DAYS'])
        ]
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)

    rv = client.get('/daily_reports_chart.json')
    result_json = json.loads(rv.data.decode('utf-8'))

    assert 'result' in result_json
    assert (len(result_json['result']) ==
            app.app.config['DAILY_REPORTS_CHART_DAYS'])
    day_format = '%Y-%m-%d'
    cur_day = datetime.strptime(result_json['result'][0]['day'], day_format)
    for day in result_json['result'][1:]:
        next_day = datetime.strptime(day['day'], day_format)
        assert cur_day < next_day
        cur_day = next_day

    assert rv.status_code == 200


def _report(apply, facts, ago=timedelta(hours=3)):
    """An agent report sent `ago` before now."""
    sent = datetime.now(timezone.utc) - ago
    return {'producer_timestamp': sent.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), 'metrics': {'href': '/x', 'data': [
        {'category': 'time', 'name': 'catalog_application', 'value': apply},
        {'category': 'time', 'name': 'fact_generation', 'value': facts},
        {'category': 'time', 'name': 'total', 'value': 99},
        {'category': 'resources', 'name': 'catalog_application', 'value': 1000},
    ]}}


class ReportsDb:
    """Answers run time queries like PuppetDB: the reports sent in the asked range."""

    def __init__(self, reports):
        self.reports = reports
        self.queries = []

    def _query(self, endpoint, query):
        self.queries.append(json.loads(str(query)))
        conditions = self.queries[-1][2][1:]
        start, end = conditions[0][2], conditions[1][2]
        return [r for r in self.reports
                if start <= r['producer_timestamp'] < end]


@pytest.fixture(autouse=True)
def clear_run_times_cache():
    dailychart._run_times_cache.clear()


def test_json_run_times_chart_min_max_avg(client, mocker,
                                          mock_puppetdb_environments,
                                          mock_puppetdb_default_nodes):
    days = app.app.config['DAILY_REPORTS_CHART_DAYS']
    reports = [_report(2, 1), _report(10.004, 3), _report(4, 2, timedelta(days=days - 2)), {
        'producer_timestamp': _report(0, 0)['producer_timestamp'], 'metrics': {'data': []}}]
    mocker.patch.object(app.puppetdb, '_query', side_effect=ReportsDb(reports)._query)

    rv = client.get('/run_times_chart.json')

    assert rv.status_code == 200
    result = json.loads(rv.data)['result']
    assert len(result) == days
    seen = [day for day in result if day['catalog_application']['max'] is not None]
    assert [day['catalog_application'] for day in seen] == [{'min': 4, 'max': 4, 'avg': 4},
                                                            {'min': 2, 'max': 10.0, 'avg': 6.0}]
    assert seen[1]['fact_generation'] == {'min': 1, 'max': 3, 'avg': 2}


def test_json_run_times_chart_no_metrics_gives_gaps(client, mocker,
                                                    mock_puppetdb_environments,
                                                    mock_puppetdb_default_nodes):
    reports = [{'producer_timestamp': _report(0, 0)['producer_timestamp'], 'metrics': None}]
    mocker.patch.object(app.puppetdb, '_query', side_effect=ReportsDb(reports)._query)

    result = json.loads(client.get('/run_times_chart.json').data)['result']

    empty = {'min': None, 'max': None, 'avg': None}
    assert all(day['catalog_application'] == empty and day['fact_generation'] == empty
               for day in result)


def test_json_run_times_chart_unknown_environment_is_404(client, mocker,
                                                        mock_puppetdb_environments,
                                                        mock_puppetdb_default_nodes):
    db = ReportsDb([])
    mocker.patch.object(app.puppetdb, '_query', side_effect=db._query)

    assert client.get('/nosuchenv/run_times_chart.json').status_code == 404
    assert client.get('/staging/run_times_chart.json').status_code == 200
    assert client.get('/*/run_times_chart.json').status_code == 200
    assert set(dailychart._run_times_cache) == {'staging', '*'}


def test_run_times_chart_query_filters_environment():
    db = ReportsDb([])
    dailychart.get_run_times_chart(db, 'production', 2)
    assert db.queries
    assert all(['=', 'environment', 'production'] in q[2] and q[1] == ['producer_timestamp', 'metrics']
               for q in db.queries)
    db.queries.clear()
    dailychart.get_run_times_chart(db, '*', 1)
    assert all('environment' not in json.dumps(q) for q in db.queries)


def test_run_times_chart_keeps_finished_hours():
    db = ReportsDb([_report(5, 1, timedelta(hours=30)), _report(7, 1, timedelta(minutes=10))])
    first = dailychart.get_run_times_chart(db, '*', 8)
    asked = len(db.queries)
    # a reload only asks for the hours that may still get reports
    db.reports = [_report(100, 1, timedelta(hours=30)), _report(9, 1, timedelta(minutes=5))]
    second = dailychart.get_run_times_chart(db, '*', 8)

    assert asked >= 1 and len(db.queries) - asked == 1
    start, end = (datetime.fromisoformat(c[2]) for c in db.queries[-1][2][1:3])
    assert end - start <= timedelta(hours=2)
    assert max(day['catalog_application']['max'] or 0 for day in first) == 7
    assert max(day['catalog_application']['max'] or 0 for day in second) == 9
    # the 30 hours old run stays as first seen
    assert all(day['catalog_application']['max'] != 100 for day in second)


def test_run_times_chart_day_and_hour_views_share_the_cache():
    db = ReportsDb([_report(3, 1, timedelta(hours=5))])
    days = dailychart.get_run_times_chart(db, 'production', 8)
    asked = len(db.queries)
    hours = dailychart.get_run_times_chart(db, 'production', 8, hourly=True)

    assert len(db.queries) - asked == 1
    assert len(hours) == 24
    assert [h['catalog_application']['avg'] for h in hours].count(3) == 1
    assert [d['catalog_application']['avg'] for d in days].count(3) == 1
    # another environment has its own cache
    dailychart.get_run_times_chart(db, 'staging', 8)
    assert len(db.queries) - asked > 2


def test_run_times_chart_drops_hours_outside_the_window():
    old = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=30)
    dailychart._run_times_cache['*'] = {old: {}}
    dailychart.get_run_times_chart(ReportsDb([]), '*', 8)
    assert old not in dailychart._run_times_cache['*']


def test_hour_stats_sums_per_hour():
    reports = [{'producer_timestamp': '2026-11-20T10:59:59.000Z', 'metrics': {'data': [
                   {'category': 'time', 'name': 'fact_generation', 'value': 2}]}},
               {'producer_timestamp': '2026-11-20T10:00:00.000Z', 'metrics': {'data': [
                   {'category': 'time', 'name': 'fact_generation', 'value': 4},
                   {'category': 'time', 'name': 'catalog_application', 'value': 1}]}},
               {'producer_timestamp': '2026-11-20T11:00:00.000Z', 'metrics': None}]
    hours = dailychart._hour_stats(reports)
    ten = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
    assert hours == {ten: {'fact_generation': [2, 4, 6, 2], 'catalog_application': [1, 1, 1, 1]},
                     ten + timedelta(hours=1): {}}
    assert dailychart._format_run_times('d', hours.values())['fact_generation'] == {'min': 2, 'max': 4, 'avg': 3}


def test_json_daily_reports_chart_today_by_hour(client, mocker,
                                                mock_puppetdb_environments,
                                                mock_puppetdb_default_nodes):
    mocker.patch.object(app.puppetdb, '_query',
                        side_effect=MockDbQuery({'reports': [[{'status': 'failed', 'count': 2}]] * 24}).get)

    result = json.loads(client.get('/daily_reports_chart.json?range=today').data)['result']

    assert len(result) == 24
    hours = [datetime.strptime(row['day'], '%Y-%m-%dT%H:%M:%SZ') for row in result]
    assert all((b - a).total_seconds() == 3600 for a, b in zip(hours, hours[1:]))
    assert hours[-1] <= datetime.now(timezone.utc).replace(tzinfo=None) < hours[-1].replace(minute=59, second=59)
    assert result[0]['failed'] == 2


def test_json_run_times_chart_today_by_hour(client, mocker,
                                            mock_puppetdb_environments,
                                            mock_puppetdb_default_nodes):
    mocker.patch.object(app.puppetdb, '_query',
                        side_effect=ReportsDb([_report(4, 2, timedelta(minutes=1))])._query)

    result = json.loads(client.get('/run_times_chart.json?range=today').data)['result']

    assert len(result) == 24
    assert result[-1]['day'].endswith(':00:00Z')
    assert result[-1]['catalog_application'] == {'min': 4, 'max': 4, 'avg': 4}


def test_hourly_ranges_query_each_hour():
    from puppetboard.views.dailychart import get_daily_reports_chart

    seen = []

    class Db:
        def _query(self, endpoint, query):
            seen.append(str(query))
            return []

    get_daily_reports_chart(Db(), '*', 8, hourly=True)
    assert len(seen) == 24
