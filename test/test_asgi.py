import asyncio

import pytest

from puppetboard import asgi


class Recorder:
    def __init__(self):
        self.scopes = []

    async def __call__(self, scope, receive, send):
        self.scopes.append(scope)


@pytest.fixture
def apps(monkeypatch):
    mcp, wsgi = Recorder(), Recorder()
    monkeypatch.setattr(asgi, 'mcp', mcp)
    monkeypatch.setattr(asgi, 'wsgi', wsgi)
    return mcp, wsgi


def call(path, root_path=''):
    scope = {'type': 'http', 'path': path, 'raw_path': path.encode(), 'root_path': root_path}
    asyncio.run(asgi.app(scope, None, None))


@pytest.mark.parametrize('path,root', [('/mcp', ''), ('/mcp/', ''), ('/pb/mcp', '/pb')])
def test_mcp_paths_go_to_mcp(apps, path, root):
    mcp, wsgi = apps
    call(path, root)
    assert len(mcp.scopes) == 1 and not wsgi.scopes
    assert mcp.scopes[0]['path'] == '/mcp' and mcp.scopes[0]['root_path'] == ''


@pytest.mark.parametrize('path', ['/', '/nodes', '/mcpx', '/api/v1/nodes', '/static/x.js'])
def test_everything_else_goes_to_flask(apps, path):
    mcp, wsgi = apps
    call(path)
    assert wsgi.scopes and not mcp.scopes


def test_without_mcp_everything_goes_to_flask(apps, monkeypatch):
    _, wsgi = apps
    monkeypatch.setattr(asgi, 'mcp', None)
    call('/mcp')
    assert wsgi.scopes


def test_lifespan_without_mcp(monkeypatch):
    monkeypatch.setattr(asgi, 'mcp', None)
    incoming = [{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}]
    sent = []

    async def receive():
        return incoming.pop(0)

    async def send(message):
        sent.append(message['type'])

    asyncio.run(asgi.app({'type': 'lifespan'}, receive, send))
    assert sent == ['lifespan.startup.complete', 'lifespan.shutdown.complete']
