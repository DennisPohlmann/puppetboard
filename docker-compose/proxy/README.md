# Puppetboard behind nginx with TLS and Basic-Auth

Puppetboard with the read-only JSON API (`/api/v1/`) and the MCP server
(`/mcp`) enabled, for an existing PuppetDB. Neither has authentication of its
own, so only nginx is published: it terminates TLS and asks for a user and
password for every request (web interface, API and MCP alike).

## Files

```bash
cd docker-compose/proxy
cp .env.example .env
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env
htpasswd -cB htpasswd admin            # more users: htpasswd -B htpasswd <name>
cp /path/to/fullchain.pem tls/cert.pem # server certificate for nginx
cp /path/to/privkey.pem   tls/key.pem
```

The PuppetDB client certificate goes to `ssl/` exactly as described in
[../standalone/README.md](../standalone/README.md#puppetdb-certificate).

In `.env` set `PUPPETDB_HOST`, `PUPPETDB_PORT` and `MCP_ALLOWED_HOSTS`: the
host name your users and MCP clients type, without port (for example
`puppetboard.example.com`). `/mcp` answers other host names with 421.

## Start

```bash
docker compose up -d        # or: podman-compose up -d
curl -u admin https://puppetboard.example.com/api/v1/nodes?status=failed
```

An MCP client, for example Claude Code:

```bash
claude mcp add --transport http puppetboard https://puppetboard.example.com/mcp \
  --header "Authorization: Basic $(printf 'admin:password' | base64)"
```

## How it is set up

- `nginx.conf`: TLS 1.2/1.3, HSTS, Basic-Auth for everything, and the
  `X-Forwarded-*` headers Puppetboard trusts from exactly this one proxy
  (client address for the rate limit and the audit log).
- Puppetboard has no published port; nginx reaches it inside the compose
  network.
- Both containers run with a read-only root file system; Puppetboard also
  drops all capabilities.
- `HTTPS_PORT` in `.env` changes the published port (default 443).
