from bs4 import BeautifulSoup

from puppetboard import app
from test import MockDbQuery


def test_get_index(client, mocker,
                   mock_puppetdb_environments,
                   mock_puppetdb_default_nodes):
    query_data = {
        'nodes': [[{'count': 10}]],
        'resources': [[{'count': 40}]],
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)
    rv = client.get('/')
    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'
    assert rv.status_code == 200
    # DataTables drops the second "very" from the class list, so the
    # compact row padding hangs on the extra very-compact class
    assert 'very-compact' in soup.select_one('#main-table')['class']
    # Report is the last column, so its sort arrow sits at the right edge;
    # the reports icon lives inside the Report cell
    headers = [th.get_text(strip=True) for th in soup.select('#main-table thead th')]
    assert headers == ['Status', 'Certname', 'Report']
    for row in soup.select('#main-table tbody tr'):
        assert len(row.find_all('td', recursive=False)) == 3
    assert soup.select('#main-table td:last-child .report-cell a.reports-link')
    charts = [c['data-metric'] for c in soup.select('.run-times-chart')]
    assert charts == ['catalog_application', 'fact_generation']
    # each chart script once, or every chart is drawn and fetched twice
    scripts = [t['src'] for t in soup.select('script[src]')]
    assert scripts.count('/static/js/dailychart.js') == 1
    assert scripts.count('/static/js/runtimes.js') == 1
    # one range switch drives the daily chart and the run time charts
    assert [b['data-range-value'] for b in soup.select('[data-range-value]')] == ['today', 'days']


def test_index_all(client, mocker,
                   mock_puppetdb_environments,
                   mock_puppetdb_default_nodes):
    # starting with v6.9.1 they changed the metric API to v2
    # and a totally different format
    base_str = 'puppetlabs.puppetdb.population:'
    query_data = {
        'version': [{'version': '6.9.1'}],
        'metrics': [
            {
                'validate': {
                    'data': {
                        'value': {'Value': 10}
                    },
                    'checks': {
                        'path': '%sname=num-nodes' % base_str
                    }
                }
            },
            {
                'validate': {
                    'data': {
                        'value': {'Value': 63}
                    },
                    'checks': {
                        'path': '%sname=num-resources' % base_str
                    }
                }
            },
            {
                'validate': {
                    'data': {
                        'value': {'Value': 6.3}
                    },
                    'checks': {
                        'path': '%sname=avg-resources-per-node' % base_str
                    }
                }
            }
        ]
    }
    dbquery = MockDbQuery(query_data)
    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)
    rv = client.get('/%2A/')

    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'
    vals = soup.find_all('h1',
                         {"class": "ui header darkblue no-margin-bottom"})

    assert len(vals) == 3
    assert vals[0].string == '10'
    assert vals[1].string == '63'
    assert vals[2].string == '         6'

    assert rv.status_code == 200


def test_index_division_by_zero(client, mocker,
                                mock_puppetdb_environments,
                                mock_puppetdb_default_nodes):
    query_data = {
        'nodes': [[{'count': 0}]],
        'resources': [[{'count': 40}]],
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)

    rv = client.get('/')

    assert rv.status_code == 200

    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'

    vals = soup.find_all('h1',
                         {"class": "ui header darkblue no-margin-bottom"})
    assert len(vals) == 3
    assert vals[2].string == '0'
