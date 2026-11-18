import json

from pypuppetdb.types import Node

from puppetboard import app
from puppetboard.views import failures


def failed_node(i):
    return Node('_', f'node{i}', report_timestamp='2013-08-01T09:57:00.000Z',
                latest_report_hash=f'{i:040x}', status_report='failed')


def test_failures_fetch_logs_in_batches(client, mocker, mock_puppetdb_environments):
    nodes = [failed_node(i) for i in range(150)]
    mocker.patch.object(app.puppetdb, 'nodes', return_value=iter(nodes))
    query = mocker.patch.object(app.puppetdb, '_query', side_effect=lambda endpoint, **kw: [
        {'hash': h, 'logs': {'data': [
            {'level': 'notice', 'source': 'Puppet', 'message': 'ok'},
            {'level': 'err', 'source': 'Puppet', 'message': f'boom {h[-3:]}'}]}}
        for h in json.loads(kw['query'])[2][2][1]])

    rv = client.get('/failures/raw')

    assert rv.status_code == 200
    page = rv.get_data(as_text=True)
    assert 'boom 000' in page and 'boom 095' in page  # 0x95 = node149
    assert query.call_count == 2  # 150 nodes in chunks of 100
    assert all(c.kwargs['request_method'] == 'POST' for c in query.call_args_list)


def test_failures_report_without_logs(client, mocker, mock_puppetdb_environments):
    mocker.patch.object(app.puppetdb, 'nodes', return_value=iter([failed_node(1)]))
    mocker.patch.object(app.puppetdb, '_query', return_value=[])
    rv = client.get('/failures')
    assert 'could not find the errors' in rv.get_data(as_text=True)


def test_latest_report_logs_empty(mocker):
    query = mocker.patch.object(app.puppetdb, '_query')
    assert failures.latest_report_logs([]) == {}
    query.assert_not_called()
