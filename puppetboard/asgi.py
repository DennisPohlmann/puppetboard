"""The entry point: the Flask web UI and API plus the MCP server on /mcp.

    gunicorn -k asgi puppetboard.asgi:app
"""
from a2wsgi import WSGIMiddleware

from puppetboard.app import app as flask_app

wsgi = WSGIMiddleware(flask_app)
mcp = None
if flask_app.config['ENABLE_MCP']:
    from puppetboard.mcp_server import McpEndpoint
    mcp = McpEndpoint(flask_app.config)


async def app(scope, receive, send):
    if scope['type'] == 'lifespan':
        if mcp:
            await mcp(scope, receive, send)
        else:
            await no_lifespan(receive, send)
        return
    root = scope.get('root_path', '')
    path = scope['path'][len(root):] if root and scope['path'].startswith(root) else scope['path']
    if mcp and scope['type'] == 'http' and path in ('/mcp', '/mcp/'):
        await mcp({**scope, 'path': '/mcp', 'raw_path': b'/mcp', 'root_path': ''}, receive, send)
    else:
        await wsgi(scope, receive, send)


async def no_lifespan(receive, send):
    while True:
        message = await receive()
        if message['type'] == 'lifespan.startup':
            await send({'type': 'lifespan.startup.complete'})
        elif message['type'] == 'lifespan.shutdown':
            await send({'type': 'lifespan.shutdown.complete'})
            return
