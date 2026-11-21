import json
from datetime import datetime, timezone

from puppetboard import app
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


def _report(apply, facts):
    return {'metrics': {'href': '/x', 'data': [
        {'category': 'time', 'name': 'catalog_application', 'value': apply},
        {'category': 'time', 'name': 'fact_generation', 'value': facts},
        {'category': 'time', 'name': 'total', 'value': 99},
        {'category': 'resources', 'name': 'catalog_application', 'value': 1000},
    ]}}


def test_json_run_times_chart_min_max_avg(client, mocker,
                                          mock_puppetdb_environments,
                                          mock_puppetdb_default_nodes):
    days = app.app.config['DAILY_REPORTS_CHART_DAYS']
    query_data = {'reports': [[_report(2, 1), _report(10.004, 3), {'metrics': {'data': []}}]] * days}
    mocker.patch.object(app.puppetdb, '_query', side_effect=MockDbQuery(query_data).get)

    rv = client.get('/run_times_chart.json')

    assert rv.status_code == 200
    result = json.loads(rv.data)['result']
    assert len(result) == days
    assert result[0]['catalog_application'] == {'min': 2, 'max': 10.0, 'avg': 6.0}
    assert result[0]['fact_generation'] == {'min': 1, 'max': 3, 'avg': 2}


def test_json_run_times_chart_no_metrics_gives_gaps(client, mocker,
                                                    mock_puppetdb_environments,
                                                    mock_puppetdb_default_nodes):
    days = app.app.config['DAILY_REPORTS_CHART_DAYS']
    mocker.patch.object(app.puppetdb, '_query',
                        side_effect=MockDbQuery({'reports': [[{'metrics': None}]] * days}).get)

    result = json.loads(client.get('/run_times_chart.json').data)['result']

    empty = {'min': None, 'max': None, 'avg': None}
    assert all(day['catalog_application'] == empty and day['fact_generation'] == empty
               for day in result)


def test_run_times_chart_query_filters_environment():
    from puppetboard.views.dailychart import get_run_times_chart

    seen = []

    class Db:
        def _query(self, endpoint, query):
            seen.append(str(query))
            return []

    get_run_times_chart(Db(), 'production', 2)
    assert len(seen) == 2
    assert all('"environment","production"' in q.replace(' ', '') and 'metrics' in q for q in seen)
    seen.clear()
    get_run_times_chart(Db(), '*', 1)
    assert 'environment' not in seen[0]



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
                        side_effect=MockDbQuery({'reports': [[_report(4, 2)]] * 24}).get)

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
