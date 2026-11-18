import asyncio
import json

import pytest
from mcp import Client
from requests.exceptions import ConnectionError

from puppetboard import app
from puppetboard.mcp_server import McpEndpoint, create_server

CONFIG = dict(app.app.config, MCP_ALLOWED_HOSTS=['puppetboard.test'], MCP_ALLOWED_ORIGINS=[],
              MCP_MAX_REQUEST_BODY=1024, API_RATE_LIMIT=0, ENABLE_QUERY=True)


@pytest.fixture
def pdb_query(mocker):
    return mocker.patch.object(app.puppetdb, '_query', return_value=[])


def call(tool, args, config=CONFIG):
    async def run():
        async with Client(create_server(config)) as client:
            return await client.call_tool(tool, args)
    return asyncio.run(run())


def tools(config=CONFIG):
    async def run():
        async with Client(create_server(config)) as client:
            return (await client.list_tools()).tools
    return asyncio.run(run())


def test_all_tools_read_only():
    found = tools()
    assert {t.name for t in found} >= {'list_nodes', 'search_fact_paths', 'find_fact_values',
                                       'get_node_facts', 'list_node_resources', 'run_pql'}
    assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint
               for t in found)


def test_pql_tool_only_with_enable_query():
    assert 'run_pql' not in {t.name for t in tools(dict(CONFIG, ENABLE_QUERY=False))}


def test_list_nodes_trims_fields(pdb_query):
    pdb_query.return_value = [{'certname': 'n1', 'latest_report_status': 'failed',
                               'facts_environment': 'x', 'cached_catalog_status': 'y'}]
    result = call('list_nodes', {'status': 'failed', 'limit': 5})
    assert not result.is_error
    row = json.loads(result.content[0].text)
    assert row['certname'] == 'n1' and 'cached_catalog_status' not in row


def test_find_fact_values_wildcard(pdb_query):
    call('find_fact_values', {'path': 'packages.*.version', 'value_regex': '^3'})
    query = json.loads(pdb_query.call_args.kwargs['query'])
    assert query == ['and', ['~>', 'path', ['packages', '.*', 'version']], ['~', 'value', '^3']]


def test_invalid_arguments_rejected(pdb_query):
    assert call('get_node', {'certname': 'bad name'}).is_error
    assert call('list_nodes', {'limit': 5000}).is_error
    assert call('search_fact_paths', {'pattern': '('}).is_error
    pdb_query.assert_not_called()


def test_puppetdb_errors_are_not_leaked(pdb_query):
    pdb_query.side_effect = ConnectionError('http://secret-pdb:8080 refused')
    result = call('list_environments', {})
    assert result.is_error
    assert 'secret-pdb' not in result.content[0].text


def request(method='POST', body=b'', headers=(), host=b'puppetboard.test'):
    scope = {'type': 'http', 'method': method, 'path': '/mcp', 'root_path': '',
             'query_string': b'', 'client': ('10.0.0.1', 1234),
             'headers': [(b'host', host), (b'content-type', b'application/json'),
                         (b'accept', b'application/json, text/event-stream'), *headers]}
    return scope, body


def asgi(endpoint, *requests):
    """Send requests to a fresh endpoint, return [(status, body)] per request."""
    results = []

    async def one(scope, body):
        sent = []

        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}

        async def send(message):
            sent.append(message)

        await endpoint(scope, receive, send)
        results.append((sent[0]['status'], b''.join(m.get('body', b'') for m in sent[1:])))

    async def run():
        async with endpoint.app.router.lifespan_context(endpoint.app):
            for scope, body in requests:
                await one(scope, body)

    asyncio.run(run())
    return results


@pytest.fixture
def endpoint():
    return McpEndpoint(CONFIG)


def test_only_post(endpoint):
    assert [r[0] for r in asgi(endpoint, request('GET'), request('DELETE'))] == [405, 405]


def test_request_without_id_refused(endpoint):
    [(status, body)] = asgi(endpoint, request(body=b'{"jsonrpc":"2.0","method":"tools/list"}'))
    assert status == 400 and b'non-null id' in body


def test_body_size_limit(endpoint):
    assert asgi(endpoint, request(body=b'x' * 2000))[0][0] == 413


def test_unsupported_protocol_version(endpoint):
    version = [(b'mcp-protocol-version', b'2024-11-05')]
    assert asgi(endpoint, request(body=b'{}', headers=version))[0][0] == 400


def test_rate_limit():
    endpoint = McpEndpoint(dict(CONFIG, API_RATE_LIMIT=1))
    assert [r[0] for r in asgi(endpoint, request('GET'), request('GET'))] == [405, 429]


def test_dns_rebinding_host_refused(endpoint):
    body = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
    assert asgi(endpoint, request(body=body, host=b'evil.example.com'))[0][0] == 421


def test_tool_call_and_audit_log(endpoint, caplog, pdb_query):
    caplog.set_level('INFO', logger='puppetboard.audit')
    body = (b'{"jsonrpc":"2.0","id":7,"method":"tools/call",'
            b'"params":{"name":"list_environments","arguments":{}}}')
    [(status, _)] = asgi(endpoint, request(body=body, headers=[
        (b'mcp-protocol-version', b'2025-06-18')]))
    line = next(r.getMessage() for r in caplog.records if r.name == 'puppetboard.audit')
    entry = json.loads(line.split(' ', 1)[1])
    assert entry['calls'] == [{'id': 7, 'rpc': 'tools/call', 'tool': 'list_environments'}]
    assert entry['client'] == '10.0.0.1'
    assert entry['status'] == status
