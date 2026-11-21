"""Read-only JSON API under /api/v1/ (see docs/API.md and openapi.json).

No authentication of its own: it is meant to run behind a reverse proxy
that terminates TLS and authenticates the client.
"""
import logging
import os
import time
from datetime import datetime, timezone

from flask import (Blueprint, abort, g, jsonify, render_template, request,
                   send_from_directory)
from requests.exceptions import ConnectionError, HTTPError, Timeout
from werkzeug.exceptions import HTTPException

from puppetboard import data
from puppetboard.core import get_app
from puppetboard.ratelimit import RateLimiter

app = get_app()
api = Blueprint('api', __name__, url_prefix='/api/v1')
audit = logging.getLogger('puppetboard.audit')
limiter = RateLimiter(app.config['API_RATE_LIMIT'])
STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'api')


def error(status, message):
    response = jsonify({'error': {'status': status, 'message': message}})
    response.status_code = status
    return response


def log_safe(value):
    """Client-controlled text for the audit log: no line breaks, no forged lines."""
    return str(value).replace('\\', '\\\\').replace('\r', '\\r').replace('\n', '\\n')


def listing(rows, limit, offset):
    return jsonify({'data': rows, 'meta': {'limit': limit, 'offset': offset, 'count': len(rows)}})


@api.before_request
def guard():
    if not app.config['ENABLE_API']:
        abort(404)
    g.api_start = time.monotonic()
    if not limiter.allow(request.remote_addr):
        response = error(429, 'rate limit exceeded')
        response.headers['Retry-After'] = limiter.retry_after()
        return response
    return None


@api.after_request
def headers_and_audit(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if 'api_start' in g:
        audit.info('api ts=%s method=%s path=%s status=%s client=%s duration_ms=%d',
                   datetime.now(timezone.utc).isoformat(), log_safe(request.method),
                   log_safe(request.full_path), response.status_code,
                   log_safe(request.remote_addr), (time.monotonic() - g.api_start) * 1000)
    return response


@api.errorhandler(data.InvalidArgument)
def invalid_argument(e):
    return error(400, str(e))


@api.errorhandler(data.Disabled)
def disabled(e):
    return error(403, str(e))


@api.errorhandler(data.NotFound)
def not_found(e):
    return error(404, str(e))


@api.errorhandler(HTTPError)
@api.errorhandler(ConnectionError)
@api.errorhandler(Timeout)
def puppetdb_error(e):
    logging.getLogger(__name__).error('PuppetDB request failed: %s', e)
    return error(502, 'PuppetDB request failed')


@api.errorhandler(HTTPException)
def http_error(e):
    return error(e.code, e.description)


def args_page():
    return data.page(request.args.get('limit'), request.args.get('offset'))


@api.route('/')
def index():
    links = {'openapi': request.base_url + 'openapi.json'}
    if app.config['API_DOCS']:
        links['docs'] = request.base_url + 'docs'
    return jsonify({'data': links})


@api.route('/openapi.json')
def openapi():
    return send_from_directory(STATIC, 'openapi.json', mimetype='application/json')


@api.route('/docs')
def docs():
    """Scalar reference of openapi.json, all assets local, no request sending."""
    if not app.config['API_DOCS']:
        abort(404)
    response = app.make_response(render_template('api_docs.html'))
    # Scalar's Vue components inject <style> tags, hence 'unsafe-inline' for styles only
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@api.route('/nodes')
def nodes():
    limit, offset = args_page()
    return listing(data.nodes(request.args.get('status'), request.args.get('environment'),
                              limit, offset), limit, offset)


@api.route('/nodes/<certname>')
def node(certname):
    return jsonify({'data': data.node(certname)})


@api.route('/nodes/<certname>/facts')
def node_facts(certname):
    names = request.args.getlist('name')
    return jsonify({'data': data.node_facts(certname, names)})


@api.route('/nodes/<certname>/reports')
def node_reports(certname):
    limit, offset = args_page()
    return listing(data.node_reports(certname, limit, offset), limit, offset)


@api.route('/nodes/<certname>/resources')
def node_resources(certname):
    limit, offset = args_page()
    rows = data.node_resources(certname, request.args.get('type'), request.args.get('title'),
                               limit, offset)
    return listing(rows, limit, offset)


@api.route('/facts/<name>')
def fact(name):
    limit, offset = args_page()
    return listing(data.fact(name, request.args.get('environment'), limit, offset),
                   limit, offset)


@api.route('/reports/<report_hash>')
def report(report_hash):
    return jsonify({'data': data.report(report_hash)})


@api.route('/query')
def query():
    rows, truncated = data.pql(request.args.get('pql'))
    return jsonify({'data': rows, 'meta': {'count': len(rows), 'truncated': truncated}})


app.register_blueprint(api)
