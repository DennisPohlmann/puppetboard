"""Read-only MCP server (Streamable HTTP) over the PuppetDB data.

It has no authentication of its own; run it behind a TLS reverse proxy that
authenticates clients. See docs/API.md for the CIS MCP benchmark mapping.
"""
import functools
import json
import logging
import time
from datetime import datetime, timezone
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import Field

from puppetboard import data
from puppetboard.ratelimit import RateLimiter
from puppetboard.version import __version__

audit = logging.getLogger('puppetboard.audit')

INSTRUCTIONS = """\
Read-only access to the Puppet infrastructure data in PuppetDB: nodes, their
facts, Puppet run reports and the resources of their catalogs.

Facts differ between sites, there is no fixed list. Before you look for some
information in facts, find the fact that holds it:
1. search_fact_names (substring) and search_fact_paths (regex on dotted paths
   into structured facts) show which facts exist.
2. get_fact_values (one top-level fact on all nodes) or find_fact_values (a
   dotted path, '*' as a wildcard element, optional value regex) then give
   values per node; get_node_facts gives facts of one node.
Example: installed packages are only in facts if a module provides such a
fact; search for 'package' to find it. Packages that Puppet manages are also
catalog resources of type 'package' (list_node_resources, if enabled).
Node status: failed, changed, unchanged, noop or unreported. Use small limits
and page with offset instead of fetching everything at once."""

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True,
                            open_world_hint=False)
NODE_FIELDS = ('certname', 'catalog_environment', 'latest_report_status', 'latest_report_noop',
               'report_timestamp', 'facts_timestamp', 'catalog_timestamp',
               'latest_report_hash', 'deactivated', 'expired')

Certname = Annotated[str, Field(description='Node certname, e.g. web01.example.com',
                                pattern=data.CERTNAME.pattern)]
Environment = Annotated[str | None, Field(description='Puppet environment, omit for all',
                                          pattern=data.ENVIRONMENT.pattern)]
Limit = Annotated[int, Field(ge=1, le=1000, description='Maximum number of rows')]
Offset = Annotated[int, Field(ge=0, description='Rows to skip, for paging')]


def tool_errors(fn):
    """Expected failures go to the model as a message, PuppetDB details do not."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (data.InvalidArgument, data.NotFound, data.Disabled) as e:
            raise ToolError(str(e)) from None
    return wrapper


def create_server(config):
    server = MCPServer(name='puppetboard', version=__version__, instructions=INSTRUCTIONS)

    def tool(fn):
        return server.tool(annotations=READ_ONLY)(tool_errors(fn))

    @tool
    def list_environments() -> list[str]:
        """Names of all Puppet environments."""
        return data.environments()

    @tool
    def list_nodes(
            status: Annotated[str | None, Field(description='Only nodes with this status', json_schema_extra={'enum': list(data.NODE_STATUSES)})] = None,  # noqa: E501 pylint: disable=line-too-long
            environment: Environment = None, limit: Limit = 50, offset: Offset = 0) -> list[dict]:
        """Active nodes with their latest report status, sorted by certname."""
        return [{k: n.get(k) for k in NODE_FIELDS}
                for n in data.nodes(status, environment, limit, offset)]

    @tool
    def get_node(certname: Certname) -> dict:
        """Status and timestamps of one node."""
        return data.node(certname)

    @tool
    def search_fact_names(
            contains: Annotated[str | None, Field(max_length=255, description='Case-insensitive substring, omit for all')] = None  # noqa: E501 pylint: disable=line-too-long
    ) -> list[str]:
        """Names of the top-level facts that exist on any node."""
        return data.fact_names(contains)

    @tool
    def search_fact_paths(
            pattern: Annotated[str, Field(min_length=1, max_length=256, description='Regex matched against each path element, e.g. package or ^os$')],  # noqa: E501 pylint: disable=line-too-long
            limit: Limit = 100, offset: Offset = 0) -> list[dict]:
        """Paths into (structured) facts, e.g. os.release.major, with their value type."""
        return data.fact_paths(pattern, limit, offset)

    @tool
    def get_node_facts(
            certname: Certname,
            names: Annotated[list[str] | None, Field(max_length=100, description='Only these top-level facts; omit for all (can be large)')] = None  # noqa: E501 pylint: disable=line-too-long
    ) -> dict[str, Any]:
        """Facts of one node as name to value."""
        return data.node_facts(certname, names)

    @tool
    def get_fact_values(
            name: Annotated[str, Field(description='Top-level fact name', pattern=data.FACT_NAME.pattern)],  # noqa: E501 pylint: disable=line-too-long
            environment: Environment = None, limit: Limit = 100, offset: Offset = 0) -> list[dict]:
        """Value of one top-level fact on every node."""
        return data.fact(name, environment, limit, offset)

    @tool
    def find_fact_values(
            path: Annotated[str, Field(min_length=1, max_length=1024, description="Dotted fact path, '*' matches one element, e.g. os.release.major or packages.*.version")],  # noqa: E501 pylint: disable=line-too-long
            value_regex: Annotated[str | None, Field(max_length=256, description='Only values matching this regex')] = None,  # noqa: E501 pylint: disable=line-too-long
            environment: Environment = None, limit: Limit = 100, offset: Offset = 0) -> list[dict]:
        """Nodes and values at a path inside structured facts."""
        return data.fact_contents(path, value_regex, environment, limit, offset)

    @tool
    def list_node_reports(certname: Certname, limit: Limit = 10, offset: Offset = 0) -> list[dict]:
        """Puppet run reports of a node, newest first, without logs."""
        return data.node_reports(certname, limit, offset)

    @tool
    def get_report(
            report_hash: Annotated[str, Field(pattern=data.REPORT_HASH.pattern, description='Report hash from list_node_reports or a node')]  # noqa: E501 pylint: disable=line-too-long
    ) -> dict:
        """One report with logs, metrics and changed resources (resource events)."""
        return data.report(report_hash)

    if config['ENABLE_CATALOG']:
        @tool
        def list_node_resources(
                certname: Certname,
                type: Annotated[str | None, Field(description='Resource type, e.g. package, file, service, class')] = None,  # noqa: E501 pylint: disable=line-too-long,redefined-builtin
                title: Annotated[str | None, Field(max_length=1024)] = None,
                limit: Limit = 100, offset: Offset = 0) -> list[dict]:
            """Resources in the latest catalog of a node."""
            return data.node_resources(certname, type, title, limit, offset)

    if config['ENABLE_QUERY']:
        @tool
        def run_pql(
                query: Annotated[str, Field(min_length=1, max_length=config['API_MAX_QUERY_LENGTH'], description='PQL, e.g. nodes[certname] { facts { name = "kernel" and value = "Linux" } }')]  # noqa: E501 pylint: disable=line-too-long
        ) -> dict:
            """Run a PuppetDB PQL query for anything the other tools cannot answer."""
            rows, truncated = data.pql(query)
            return {'rows': rows, 'truncated': truncated}

    return server


def forwarded_client(scope):
    """Client address, trusting one proxy hop like the Flask app's ProxyFix."""
    for name, value in scope.get('headers', []):
        if name == b'x-forwarded-for':
            return value.decode('latin-1').split(',')[-1].strip()
    return (scope.get('client') or ('-',))[0]


class McpEndpoint:
    """ASGI app for /mcp: rate limit, size limit, JSON-RPC checks and audit log
    in front of the SDK's stateless Streamable HTTP transport."""

    def __init__(self, config):
        if not config['MCP_ALLOWED_HOSTS']:
            logging.getLogger(__name__).error(
                'MCP_ALLOWED_HOSTS is empty, every /mcp request will be refused')
        self.max_body = config['MCP_MAX_REQUEST_BODY']
        self.versions = config['MCP_PROTOCOL_VERSIONS']
        self.limiter = RateLimiter(config['API_RATE_LIMIT'])
        self.app = create_server(config).streamable_http_app(
            streamable_http_path='/mcp', stateless_http=True, json_response=True,
            max_request_body_size=self.max_body,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=config['MCP_ALLOWED_HOSTS'],
                allowed_origins=config['MCP_ALLOWED_ORIGINS']))

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            await self.app(scope, receive, send)
            return
        start = time.monotonic()
        client = forwarded_client(scope)
        headers = {k.decode('latin-1').lower(): v.decode('latin-1')
                   for k, v in scope.get('headers', [])}
        version = headers.get('mcp-protocol-version', '-')
        entry = {'ts': datetime.now(timezone.utc).isoformat(), 'client': client,
                 'method': scope['method'], 'protocol': version}
        status = [0]

        async def send_logged(message):
            if message['type'] == 'http.response.start':
                status[0] = message['status']
            await send(message)

        try:
            if not self.limiter.allow(client):
                await plain(send_logged, 429, 'rate limit exceeded',
                            [(b'retry-after', self.limiter.retry_after().encode())])
            elif version != '-' and version not in self.versions:
                await plain(send_logged, 400, 'unsupported MCP protocol version')
            elif scope['method'] != 'POST':
                # stateless JSON mode: no SSE stream (GET) and no sessions (DELETE)
                await plain(send_logged, 405, 'only POST is supported', [(b'allow', b'POST')])
            else:
                body = await read_body(receive, self.max_body)
                problem = None if body is not None else (413, 'request body too large')
                if problem is None:
                    problem = check_jsonrpc(body, entry)
                if problem:
                    await plain(send_logged, *problem)
                else:
                    await self.app(scope, replay(body), send_logged)
        finally:
            entry.update(status=status[0], duration_ms=int((time.monotonic() - start) * 1000))
            audit.info('mcp %s', json.dumps(entry, sort_keys=True))


async def read_body(receive, limit):
    body = b''
    while True:
        message = await receive()
        body += message.get('body', b'')
        if len(body) > limit:
            return None
        if not message.get('more_body'):
            return body


def replay(body):
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {'type': 'http.disconnect'}
        sent = True
        return {'type': 'http.request', 'body': body, 'more_body': False}
    return receive


def check_jsonrpc(body, entry):
    """Record method, id and tool for the audit log; refuse requests without id."""
    try:
        payload = json.loads(body)
    except ValueError:
        return 400, 'invalid JSON'
    messages = payload if isinstance(payload, list) else [payload]
    for msg in messages:
        if not isinstance(msg, dict):
            return 400, 'invalid JSON-RPC message'
        method = msg.get('method')
        if method == 'initialize':
            entry['protocol'] = (msg.get('params') or {}).get('protocolVersion')
        entry.setdefault('calls', []).append({
            'rpc': method, 'id': msg.get('id'),
            'tool': (msg.get('params') or {}).get('name') if method == 'tools/call' else None})
        if isinstance(method, str) and not method.startswith('notifications/') \
                and msg.get('id') is None:
            return 400, 'JSON-RPC requests need a non-null id'
    return None


async def plain(send, status, text, extra_headers=()):
    await send({'type': 'http.response.start', 'status': status,
                'headers': [(b'content-type', b'text/plain; charset=utf-8'), *extra_headers]})
    await send({'type': 'http.response.body', 'body': text.encode()})
