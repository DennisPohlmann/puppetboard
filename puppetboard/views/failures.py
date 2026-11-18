import json

from flask import Response, stream_with_context, abort
from pypuppetdb.QueryBuilder import AndOperator, EqualsOperator

from puppetboard.core import get_app, get_puppetdb, environments, stream_template, to_html, \
    get_friendly_error, get_raw_error
from puppetboard.utils import check_env, get_or_abort, yield_or_stop

app = get_app()
puppetdb = get_puppetdb()


@app.route('/failures', defaults={'env': app.config['DEFAULT_ENVIRONMENT'],
                                  'show_error_as': app.config['SHOW_ERROR_AS']})
@app.route('/failures/<show_error_as>', defaults={'env': app.config['DEFAULT_ENVIRONMENT']})
@app.route('/<env>/failures', defaults={'show_error_as': app.config['SHOW_ERROR_AS']})
@app.route('/<env>/failures/<show_error_as>')
def failures(env: str, show_error_as: str):
    nodes_query = AndOperator()
    nodes_query.add(EqualsOperator('latest_report_status', 'failed'))

    envs = environments()
    check_env(env, envs)
    if env != '*':
        nodes_query.add(EqualsOperator("catalog_environment", env))

    if show_error_as not in ['friendly', 'raw']:
        abort(404)

    nodes = puppetdb.nodes(
        query=nodes_query,
        with_status=True,
        with_event_numbers=False,
    )

    nodes = list(yield_or_stop(nodes))
    logs = latest_report_logs([node.latest_report_hash for node in nodes])
    failures = []

    for node in nodes:
        source = None
        message = None
        for log in logs.get(node.latest_report_hash, []):
            if log['level'] not in ['info', 'notice', 'warning']:
                if log['source'] != 'Facter':
                    source = log['source']
                    message = log['message']
                    break

        if source and message:
            if show_error_as == 'friendly':
                error = to_html(get_friendly_error(source, message, node.name))
            else:
                error = get_raw_error(source, message)
        else:
            error = to_html(f'Node {node.name} is failing but we could not find the errors')

        failure = {
            'certname': node.name,
            'timestamp': node.report_timestamp,
            'error': error,
            'report_hash': node.latest_report_hash,
        }
        failures.append(failure)

    return Response(stream_with_context(
        stream_template('failures.html',
                        failures=failures,
                        envs=envs,
                        current_env=env,
                        current_show_error_as=show_error_as)))


def latest_report_logs(hashes, chunk=100):
    """Logs of the given reports as {hash: logs}, a few queries instead of one per node."""
    logs = {}
    for i in range(0, len(hashes), chunk):
        query = ['extract', ['hash', 'logs'],
                 ['in', 'hash', ['array', hashes[i:i + chunk]]]]
        # POST: a GET URL with 100 hashes would exceed the request line limit
        rows = get_or_abort(puppetdb._query, 'reports', query=json.dumps(query),
                            request_method='POST')
        for row in rows:
            logs[row['hash']] = (row.get('logs') or {}).get('data', [])
    return logs
