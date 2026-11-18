"""Node-controlled PuppetDB data and URL parameters must never reach a page as HTML."""
import json

from markupsafe import Markup
from pypuppetdb.types import Fact, Node

from puppetboard import app
from puppetboard.core import get_raw_error, to_html
from puppetboard.utils import jsonprint
from test import MockDbQuery

XSS = '<img src=x onerror=alert(1)>'
ESCAPED = '&lt;img src=x onerror=alert(1)&gt;'


def assert_no_markup(body):
    assert '<img src=x' not in body


def test_jsonprint_escapes_strings_but_keeps_safe_markup():
    assert json.loads(jsonprint(XSS)) == ESCAPED
    assert json.loads(jsonprint({'k': [XSS]})) == {'k': [ESCAPED]}
    assert json.loads(jsonprint(Markup('<a href="/x">ok</a>'))) == '<a href="/x">ok</a>'
    assert json.loads(jsonprint(5)) == 5


def test_log_message_helpers_escape():
    assert '<img' not in get_raw_error('Puppet', XSS)
    assert '<img' not in get_raw_error(XSS, 'line1\nline2')
    assert to_html('a\n' + XSS) == 'a<br/>' + ESCAPED


def test_failures_page_escapes_log_message(client, mocker, mock_puppetdb_environments):
    node = Node('_', 'node1', report_timestamp='2013-08-01T09:57:00.000Z',
                latest_report_hash='a' * 40, status_report='failed')
    mocker.patch.object(app.puppetdb, 'nodes', side_effect=lambda **kw: iter([node]))
    mocker.patch.object(app.puppetdb, '_query', return_value=[
        {'hash': 'a' * 40, 'logs': {'data': [{'level': 'err', 'source': 'Puppet', 'message': XSS}]}}])
    for path in ('/failures', '/failures/raw'):
        body = client.get(path).get_data(as_text=True)
        assert ESCAPED in body
        assert_no_markup(body)


def test_report_page_escapes_version_and_logs(client, mocker, mock_puppetdb_environments):
    report = {
        'hash': '1234567', 'receive_time': '2022-05-11T04:00:00.000Z', 'report_format': 12,
        'puppet_version': '8.10.0', 'start_time': '2022-05-11T03:59:00.000Z',
        'end_time': '2022-05-11T04:00:00.000Z', 'producer_timestamp': '2022-05-11T04:00:00.000Z',
        'producer': 'p', 'transaction_uuid': 't', 'status': 'failed', 'noop': False,
        'noop_pending': False, 'environment': 'production', 'configuration_version': XSS,
        'certname': 'node1', 'code_id': None, 'catalog_uuid': 'c', 'cached_catalog_status': 'not_used',
        'resource_events': [], 'metrics': {'data': []},
        'logs': {'data': [{'level': 'err', 'source': 'Puppet', 'message': XSS, 'tags': [],
                           'time': '2022-05-11T04:00:00.000Z', 'file': None, 'line': None}]},
    }
    mocker.patch.object(app.puppetdb, '_query', side_effect=MockDbQuery({'reports': [[report]], 'events': [[]]}).get)
    body = client.get('/report/node1/1234567').get_data(as_text=True)
    assert_no_markup(body)
    assert '<!-- raw HTML omitted -->' in body  # configuration_version
    assert '\\u0026lt;img' in body  # log message escaped before it goes to DataTables


def test_inventory_json_escapes_facts_and_certnames(client, mocker, mock_puppetdb_environments):
    certname = 'evil"><img src=x onerror=alert(1)>'
    mocker.patch.object(app.puppetdb, 'facts', return_value=[
        Fact(certname, 'kernelrelease', XSS, 'production'),
        Fact(certname, 'trusted', {'certname': certname, 'hostname': XSS}, 'production'),
    ])
    body = client.get('/inventory/json').get_data(as_text=True)
    cells = json.loads(body)['data'][0]
    assert not any('<img' in cell for cell in cells)
    assert ESCAPED in ''.join(cells)


def test_fact_table_json_escapes_name_and_certname(client, mocker, mock_puppetdb_environments):
    # the value itself stays JSON data; the browser renders it with pretty_print (escaped)
    mocker.patch.object(app.puppetdb, 'facts', return_value=[Fact(XSS, XSS, 'v', 'production')])
    rows = json.loads(client.get('/fact/kernel/json').get_data(as_text=True))['data']
    assert rows[0][0] == '<a href="/node/%3Cimg%20src=x%20onerror=alert(1)%3E">' + ESCAPED + '</a>'
    rows = json.loads(client.get('/node/x/facts/json').get_data(as_text=True))['data']
    assert rows[0][0] == ESCAPED


def test_catalog_compare_parameter_is_escaped(client, mocker, mock_puppetdb_environments):
    app.app.config['ENABLE_CATALOG'] = True
    try:
        node = Node('_', 'node1', catalog_timestamp='2013-08-01T09:57:00.000Z')
        mocker.patch.object(app.puppetdb, 'nodes', return_value=iter([node]))
        app.puppetdb.last_total = 1
        body = client.get('/catalogs/compare/%22%3E' + XSS.replace(' ', '%20') + '/json').get_data(as_text=True)
    finally:
        app.app.config['ENABLE_CATALOG'] = False
    assert 'Compare with &#34;&gt;&lt;img' in json.loads(body)['data'][0][-1]


def test_metric_long_name_is_escaped(client, mocker, mock_puppetdb_environments):
    mocker.patch.object(app.puppetdb, 'metric', return_value={})
    name = 'a' * 60 + '<script>alert(1)</script>' + 'b' * 20
    body = client.get('/metric/' + name).get_data(as_text=True)
    assert '<script>alert(1)' not in body
    assert '&lt;script&gt;' in body


def test_fact_value_string_is_escaped_once(client, mocker, mock_puppetdb_environments):
    mocker.patch.object(app.puppetdb, 'facts', return_value=[])
    body = client.get('/fact/kernel/x%27y%26z%5C').get_data(as_text=True)
    # a JS string literal from tojson: pretty_print escapes it once, a backslash cannot end it
    assert 'pretty_print("x\\u0027y\\u0026z\\\\")' in body
