"""Read-only PuppetDB access shared by the JSON API and the MCP server.

Every function validates its arguments and returns plain JSON data as
PuppetDB delivers it. Nothing here writes to PuppetDB.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from requests.exceptions import HTTPError

from puppetboard.core import get_app, get_puppetdb

CERTNAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$')
FACT_NAME = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.:-]{0,254}$')
ENVIRONMENT = re.compile(r'^[A-Za-z0-9_]{1,255}$')
REPORT_HASH = re.compile(r'^[0-9a-f]{40}$')
RESOURCE_TYPE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(::[A-Za-z][A-Za-z0-9_]*)*$')
NODE_STATUSES = ('failed', 'changed', 'unchanged', 'noop', 'unreported')
REPORT_FIELDS = ['hash', 'certname', 'environment', 'status', 'noop', 'noop_pending',
                 'corrective_change', 'start_time', 'end_time', 'receive_time',
                 'producer_timestamp', 'puppet_version', 'configuration_version',
                 'transaction_uuid', 'cached_catalog_status', 'type']


class InvalidArgument(ValueError):
    pass


class NotFound(LookupError):
    pass


class Disabled(PermissionError):
    pass


def check(pattern, value, what):
    if not isinstance(value, str) or not pattern.match(value):
        raise InvalidArgument(f'invalid {what}')
    return value


def page(limit, offset):
    """Validate paging arguments against the configured bounds."""
    config = get_app().config
    try:
        limit = config['API_DEFAULT_LIMIT'] if limit is None else int(limit)
        offset = 0 if offset is None else int(offset)
    except (TypeError, ValueError):
        raise InvalidArgument('limit and offset must be integers') from None
    if not 1 <= limit <= config['API_MAX_LIMIT']:
        raise InvalidArgument(f"limit must be between 1 and {config['API_MAX_LIMIT']}")
    if offset < 0:
        raise InvalidArgument('offset must not be negative')
    return limit, offset


def _query(endpoint, query=None, path=None, order_by=None, limit=None, offset=None):
    try:
        return get_puppetdb()._query(
            endpoint, path=path,
            query=json.dumps(query) if query is not None else None,
            order_by=json.dumps(order_by) if order_by else None,
            limit=limit, offset=offset)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise NotFound('not found') from None
        raise


def _and(*clauses):
    clauses = [c for c in clauses if c]
    return clauses[0] if len(clauses) == 1 else ['and', *clauses]


def _env(environment):
    if environment in (None, '', '*'):
        return None
    return check(ENVIRONMENT, environment, 'environment')


def environments():
    return [e['name'] for e in _query('environments')]


def nodes(status=None, environment=None, limit=None, offset=None):
    limit, offset = page(limit, offset)
    clauses = [['=', 'node_state', 'active']]
    env = _env(environment)
    if env:
        clauses.append(['=', 'catalog_environment', env])
    if status in ('failed', 'changed', 'unchanged'):
        clauses.append(['=', 'latest_report_status', status])
    elif status == 'noop':
        clauses.append(['=', 'latest_report_noop', True])
    elif status == 'unreported':
        hours = get_app().config['UNRESPONSIVE_HOURS']
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        clauses.append(['or', ['null?', 'report_timestamp', True],
                        ['<', 'report_timestamp', cutoff]])
    elif status not in (None, ''):
        raise InvalidArgument(f"status must be one of {', '.join(NODE_STATUSES)}")
    return _query('nodes', _and(*clauses), order_by=[{'field': 'certname'}],
                  limit=limit, offset=offset)


def node(certname):
    return _query('nodes', path=check(CERTNAME, certname, 'certname'))


def node_facts(certname, names=None):
    """All facts of a node as {name: value}, optionally only the given names."""
    check(CERTNAME, certname, 'certname')
    clauses = [['=', 'certname', certname]]
    if names:
        clauses.append(['in', 'name', ['array', [check(FACT_NAME, n, 'fact name')
                                                for n in names]]])
    rows = _query('facts', _and(*clauses))
    if not rows:
        node(certname)  # raises NotFound for unknown nodes
    return {row['name']: row['value'] for row in rows}


def fact(name, environment=None, limit=None, offset=None):
    """The value of one top-level fact on every node."""
    limit, offset = page(limit, offset)
    clauses = [['=', 'name', check(FACT_NAME, name, 'fact name')]]
    env = _env(environment)
    if env:
        clauses.append(['=', 'environment', env])
    return [{'certname': r['certname'], 'environment': r['environment'], 'value': r['value']}
            for r in _query('facts', _and(*clauses), order_by=[{'field': 'certname'}],
                            limit=limit, offset=offset)]


def fact_names(pattern=None):
    names = _query('fact-names')
    if pattern:
        pattern = pattern.lower()
        names = [n for n in names if pattern in n.lower()]
    return names


def fact_paths(pattern, limit=None, offset=None):
    """Paths into structured facts whose dotted form contains pattern (regex)."""
    limit, offset = page(limit, offset)
    _regex(pattern)
    rows = _query('fact-paths', ['~', 'path', pattern], order_by=[{'field': 'path'}],
                  limit=limit, offset=offset)
    return [{'path': '.'.join(str(p) for p in r['path']), 'type': r['type']} for r in rows]


def fact_contents(path, value=None, environment=None, limit=None, offset=None):
    """Nodes and values for a dotted fact path, '*' matches one path element.

    value is an optional regex on the value.
    """
    limit, offset = page(limit, offset)
    if not isinstance(path, str) or not path or len(path) > 1024:
        raise InvalidArgument('invalid path')
    parts = path.split('.')
    if '*' in parts:
        clauses = [['~>', 'path', [re.escape(p) if p != '*' else '.*' for p in parts]]]
    else:
        clauses = [['=', 'path', parts]]
    if value not in (None, ''):
        clauses.append(['~', 'value', _regex(value)])
    env = _env(environment)
    if env:
        clauses.append(['=', 'environment', env])
    rows = _query('fact-contents', _and(*clauses), order_by=[{'field': 'certname'}],
                  limit=limit, offset=offset)
    return [{'certname': r['certname'], 'environment': r['environment'],
             'path': '.'.join(str(p) for p in r['path']), 'value': r['value']} for r in rows]


def node_reports(certname, limit=None, offset=None):
    limit, offset = page(limit, offset)
    check(CERTNAME, certname, 'certname')
    return _query('reports', ['extract', REPORT_FIELDS, ['=', 'certname', certname]],
                  order_by=[{'field': 'producer_timestamp', 'order': 'desc'}],
                  limit=limit, offset=offset)


def report(report_hash):
    """One report with its logs, metrics and resource events."""
    check(REPORT_HASH, report_hash, 'report hash')
    rows = _query('reports', ['extract', REPORT_FIELDS + ['logs', 'metrics', 'resource_events'],
                              ['=', 'hash', report_hash]])
    if not rows:
        raise NotFound('report not found')
    result = rows[0]
    for key in ('logs', 'metrics', 'resource_events'):
        result[key] = (result.get(key) or {}).get('data', [])
    return result


def resource_type(value):
    """Puppet resource types are capitalised per namespace segment."""
    check(RESOURCE_TYPE, value, 'resource type')
    return '::'.join(p.capitalize() for p in value.split('::'))


def node_resources(certname, type_=None, title=None, limit=None, offset=None):
    limit, offset = page(limit, offset)
    clauses = [['=', 'certname', check(CERTNAME, certname, 'certname')]]
    if type_:
        clauses.append(['=', 'type', resource_type(type_)])
    if title:
        if not isinstance(title, str) or len(title) > 1024:
            raise InvalidArgument('invalid title')
        clauses.append(['=', 'title', title])
    return _query('resources', _and(*clauses),
                  order_by=[{'field': 'type'}, {'field': 'title'}], limit=limit, offset=offset)


def pql(query):
    """Run a PQL query, only when the query feature is enabled.

    Returns (rows, truncated) with at most API_MAX_LIMIT rows.
    """
    config = get_app().config
    if not config['ENABLE_QUERY'] or 'pql' not in config.get('ENABLED_QUERY_ENDPOINTS', ['pql']):
        raise Disabled('PQL queries are disabled (ENABLE_QUERY)')
    if not isinstance(query, str) or not query.strip():
        raise InvalidArgument('query is required')
    if len(query) > config['API_MAX_QUERY_LENGTH']:
        raise InvalidArgument(f"query longer than {config['API_MAX_QUERY_LENGTH']} characters")
    try:
        rows = get_puppetdb()._pql(query)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            raise InvalidArgument(f'PuppetDB rejected the query: {e.response.text[:500]}') from None
        raise
    cap = config['API_MAX_LIMIT']
    return rows[:cap], len(rows) > cap


def _regex(pattern):
    if not isinstance(pattern, str) or not pattern or len(pattern) > 256:
        raise InvalidArgument('invalid pattern')
    try:
        re.compile(pattern)
    except re.error:
        raise InvalidArgument('invalid regular expression') from None
    return pattern
