import json

import pytest
from requests import Response
from requests.exceptions import ConnectionError, HTTPError

from puppetboard import app
from puppetboard.views import api


@pytest.fixture
def api_client(client):
    app.app.config['ENABLE_API'] = True
    api.limiter.per_minute = 0
    yield client
    app.app.config['ENABLE_API'] = False


@pytest.fixture
def pdb_query(mocker):
    return mocker.patch.object(app.puppetdb, '_query', return_value=[])


def http_error(status):
    response = Response()
    response.status_code = status
    return HTTPError(response=response)


def sent(pdb_query, call=-1):
    args, kwargs = pdb_query.call_args_list[call]
    return args[0], kwargs


def test_disabled_by_default(client, pdb_query):
    rv = client.get('/api/v1/nodes')
    assert rv.status_code == 404
    assert rv.json['error']['status'] == 404
    pdb_query.assert_not_called()


def test_nodes_status_filter(api_client, pdb_query):
    pdb_query.return_value = [{'certname': 'node1'}]
    rv = api_client.get('/api/v1/nodes?status=failed&environment=production&limit=5&offset=10')
    assert rv.status_code == 200
    assert rv.json == {'data': [{'certname': 'node1'}],
                       'meta': {'limit': 5, 'offset': 10, 'count': 1}}
    assert rv.headers['Cache-Control'] == 'no-store'
    endpoint, kwargs = sent(pdb_query)
    assert endpoint == 'nodes'
    assert json.loads(kwargs['query']) == [
        'and', ['=', 'node_state', 'active'], ['=', 'catalog_environment', 'production'],
        ['=', 'latest_report_status', 'failed']]
    assert (kwargs['limit'], kwargs['offset']) == (5, 10)


def test_nodes_unreported(api_client, pdb_query):
    api_client.get('/api/v1/nodes?status=unreported')
    query = json.loads(sent(pdb_query)[1]['query'])
    assert query[2][0] == 'or'


@pytest.mark.parametrize('url', [
    '/api/v1/nodes?status=bogus',
    '/api/v1/nodes?limit=0',
    '/api/v1/nodes?limit=100000',
    '/api/v1/nodes?offset=-1',
    '/api/v1/nodes?limit=abc',
    '/api/v1/nodes?environment=prod;drop',
    '/api/v1/nodes/bad%20name',
    '/api/v1/nodes/node1/resources?type=Pack%20age',
    '/api/v1/reports/notahash',
    '/api/v1/facts/os%20name',
])
def test_invalid_input(api_client, pdb_query, url):
    rv = api_client.get(url)
    assert rv.status_code == 400
    pdb_query.assert_not_called()


def test_node_not_found(api_client, pdb_query):
    pdb_query.side_effect = http_error(404)
    rv = api_client.get('/api/v1/nodes/missing.example.com')
    assert rv.status_code == 404


def test_puppetdb_down(api_client, pdb_query):
    pdb_query.side_effect = ConnectionError('down')
    rv = api_client.get('/api/v1/nodes')
    assert rv.status_code == 502
    assert 'down' not in rv.get_data(as_text=True)


def test_node_facts(api_client, pdb_query):
    pdb_query.return_value = [{'name': 'os', 'value': {'family': 'RedHat'}},
                              {'name': 'kernel', 'value': 'Linux'}]
    rv = api_client.get('/api/v1/nodes/node1/facts?name=os&name=kernel')
    assert rv.json['data'] == {'os': {'family': 'RedHat'}, 'kernel': 'Linux'}
    assert json.loads(sent(pdb_query)[1]['query'])[2] == ['in', 'name', ['array', ['os', 'kernel']]]


def test_node_facts_unknown_node(api_client, pdb_query):
    pdb_query.side_effect = [[], http_error(404)]
    assert api_client.get('/api/v1/nodes/node1/facts').status_code == 404


def test_resources_type_is_capitalised(api_client, pdb_query):
    api_client.get('/api/v1/nodes/node1/resources?type=apache::vhost')
    assert ['=', 'type', 'Apache::Vhost'] in json.loads(sent(pdb_query)[1]['query'])


def test_report_inlines_details(api_client, pdb_query):
    pdb_query.return_value = [{'hash': 'a' * 40, 'logs': {'data': [{'message': 'x'}]},
                               'metrics': {'data': []}, 'resource_events': None}]
    rv = api_client.get('/api/v1/reports/' + 'a' * 40)
    assert rv.json['data']['logs'] == [{'message': 'x'}]
    assert rv.json['data']['resource_events'] == []


def test_query_disabled(api_client, mocker):
    pql = mocker.patch.object(app.puppetdb, '_pql')
    app.app.config['ENABLE_QUERY'] = False
    try:
        assert api_client.get('/api/v1/query?pql=nodes{}').status_code == 403
    finally:
        app.app.config['ENABLE_QUERY'] = True
    pql.assert_not_called()


def test_query_truncates(api_client, mocker):
    mocker.patch.object(app.puppetdb, '_pql', return_value=[{'n': i} for i in range(1001)])
    rv = api_client.get('/api/v1/query?pql=nodes{}')
    assert rv.json['meta'] == {'count': 1000, 'truncated': True}


def test_query_too_long(api_client, mocker):
    pql = mocker.patch.object(app.puppetdb, '_pql')
    assert api_client.get('/api/v1/query?pql=' + 'x' * 5000).status_code == 400
    pql.assert_not_called()


def test_read_only(api_client, pdb_query):
    rv = api_client.post('/api/v1/nodes')
    assert rv.status_code == 405
    assert rv.json['error']['status'] == 405


def test_unknown_api_path_is_json(api_client):
    rv = api_client.get('/api/v1/no/such/thing')
    assert rv.status_code == 404
    assert rv.json['error']['message'] == 'not found'


def test_rate_limit(api_client, pdb_query):
    api.limiter.per_minute = 2
    api.limiter._counts = {}
    codes = [api_client.get('/api/v1/nodes').status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_openapi(api_client):
    rv = api_client.get('/api/v1/openapi.json')
    assert rv.status_code == 200
    assert rv.json['openapi'].startswith('3.')
    assert '/nodes/{certname}/facts' in rv.json['paths']


def test_audit_log_cannot_be_forged():
    assert api.log_safe('a\r\nfake line\\') == 'a\\r\\nfake line\\\\'
