import json

import pytest
from requests import Response
from requests.exceptions import HTTPError

from puppetboard import app, data


@pytest.fixture
def pdb_query(mocker):
    return mocker.patch.object(app.puppetdb, '_query', return_value=[])


def sent_query(mock):
    return json.loads(mock.call_args.kwargs['query'])


def http_error(status, text=''):
    response = Response()
    response.status_code = status
    response._content = text.encode()
    return HTTPError(response=response)


def test_fact_names_filter(pdb_query):
    pdb_query.return_value = ['os', 'installed_packages', 'Package_list', 'kernel']
    assert data.fact_names('pack') == ['installed_packages', 'Package_list']
    assert data.fact_names() == pdb_query.return_value


def test_fact_paths_dotted(pdb_query):
    pdb_query.return_value = [{'path': ['os', 'release', 'major'], 'type': 'string'},
                              {'path': ['disks', 0, 'size'], 'type': 'integer'}]
    assert data.fact_paths('release|size') == [
        {'path': 'os.release.major', 'type': 'string'}, {'path': 'disks.0.size', 'type': 'integer'}]
    assert sent_query(pdb_query) == ['~', 'path', 'release|size']


@pytest.mark.parametrize('pattern', ['', '(', 'x' * 300, None])
def test_fact_paths_bad_pattern(pdb_query, pattern):
    with pytest.raises(data.InvalidArgument):
        data.fact_paths(pattern)
    pdb_query.assert_not_called()


def test_fact_contents_literal_path(pdb_query):
    data.fact_contents('os.release.major', environment='production')
    assert sent_query(pdb_query) == ['and', ['=', 'path', ['os', 'release', 'major']],
                                     ['=', 'name', 'os'], ['=', 'environment', 'production']]


def test_fact_contents_leading_wildcard_has_no_name_filter(pdb_query):
    data.fact_contents('*.version')
    assert sent_query(pdb_query) == ['~>', 'path', ['.*', '^version$']]


def test_nodes_unreported_uses_utc_cutoff(pdb_query):
    data.nodes('unreported')
    clause = sent_query(pdb_query)[2]
    assert clause[0] == 'or' and clause[2][2].endswith('+00:00')


def test_environment_all_means_no_filter(pdb_query):
    data.nodes(environment='*')
    assert sent_query(pdb_query) == ['=', 'node_state', 'active']


def test_report_not_found(pdb_query):
    with pytest.raises(data.NotFound):
        data.report('a' * 40)


def test_node_resources_title_too_long(pdb_query, mocker):
    mocker.patch.dict(app.app.config, ENABLE_CATALOG=True)
    with pytest.raises(data.InvalidArgument):
        data.node_resources('node1', title='x' * 2000)


def test_node_resources_need_enable_catalog(pdb_query, mocker):
    mocker.patch.dict(app.app.config, ENABLE_CATALOG=False)
    with pytest.raises(data.Disabled):
        data.node_resources('node1')
    pdb_query.assert_not_called()


def test_pql_syntax_error_is_invalid_argument(mocker):
    mocker.patch.object(app.puppetdb, '_pql', side_effect=http_error(400, 'PQL parse error'))
    with pytest.raises(data.InvalidArgument, match='PQL parse error'):
        data.pql('nodes{bad')


def test_pql_server_error_is_not_hidden_as_user_error(mocker):
    mocker.patch.object(app.puppetdb, '_pql', side_effect=http_error(500))
    with pytest.raises(HTTPError):
        data.pql('nodes{}')


def test_puppetdb_404_becomes_not_found(pdb_query):
    pdb_query.side_effect = http_error(404)
    with pytest.raises(data.NotFound):
        data.node('node1')
