# JSON API and MCP server

Puppetboard can serve a read-only JSON API under `/api/v1/` and a read-only
[MCP](https://modelcontextprotocol.io) server under `/mcp`.

## JSON API

The API It reads the
same PuppetDB data as the web interface and never writes to PuppetDB.

The API has **no authentication of its own**. Run it behind a reverse proxy
that terminates TLS and authenticates clients (for example HTTP Basic-Auth),
see [Securing API and MCP](#securing-api-and-mcp).

### API settings

| Setting | Docker variable | Default | Meaning |
|---|---|---|---|
| `ENABLE_API` | `ENABLE_API` | `False` | Serve `/api/v1/`. When off every API URL answers 404. |
| `API_DEFAULT_LIMIT` | `API_DEFAULT_LIMIT` | `100` | Page size when `limit` is not given. |
| `API_MAX_LIMIT` | `API_MAX_LIMIT` | `1000` | Largest allowed `limit`, also caps PQL results (after PuppetDB returned them, so a broad query still costs worker memory). |
| `API_MAX_QUERY_LENGTH` | `API_MAX_QUERY_LENGTH` | `4096` | Longest accepted PQL query. |
| `API_RATE_LIMIT` | `API_RATE_LIMIT` | `120` | Requests per minute and client IP (API and MCP), `0` turns it off. Counted per worker process. |
| `ENABLE_QUERY` | `ENABLE_QUERY` | `True` | Also gates `/api/v1/query` (and `ENABLED_QUERY_ENDPOINTS` must contain `pql`). PQL reads every PuppetDB entity, catalogs and resource parameters included, regardless of `ENABLE_CATALOG`. |
| `ENABLE_CATALOG` | `ENABLE_CATALOG` | `False` | Also gates `/api/v1/nodes/<certname>/resources`; resource parameters can hold secrets. |

### Endpoints

The machine-readable description is served at `/api/v1/openapi.json`
(OpenAPI 3.1). All endpoints are `GET` only.

| Endpoint | Returns |
|---|---|
| `/api/v1/nodes?status=&environment=` | Active nodes. `status` is one of `failed`, `changed`, `unchanged`, `noop`, `unreported`. |
| `/api/v1/nodes/<certname>` | One node. |
| `/api/v1/nodes/<certname>/facts?name=` | Facts of the node as `{name: value}`. Repeat `name` to get only some facts. |
| `/api/v1/facts/<name>?environment=` | One top-level fact on every node. |
| `/api/v1/nodes/<certname>/reports` | Report summaries of the node, newest first. |
| `/api/v1/reports/<hash>` | One report with logs, metrics and resource events. |
| `/api/v1/nodes/<certname>/resources?type=&title=` | Catalog resources of the node, e.g. `type=package`, only with `ENABLE_CATALOG`. |
| `/api/v1/query?pql=` | Result of a PQL query, only with `ENABLE_QUERY`. |

List endpoints take `limit` and `offset` and answer

```json
{"data": [...], "meta": {"limit": 100, "offset": 0, "count": 42}}
```

`count` below `limit` means there is no further page. Single objects come as
`{"data": {...}}`. Errors always look like

```json
{"error": {"status": 400, "message": "invalid certname"}}
```

| Status | When |
|---|---|
| 400 | Invalid parameter (certname, fact name, hash, status, limit, PQL syntax). |
| 403 | PQL query while `ENABLE_QUERY` is off, resources while `ENABLE_CATALOG` is off. |
| 404 | Unknown node or report, or the API is disabled. |
| 405 | Any method other than `GET`. |
| 429 | Rate limit hit, see the `Retry-After` header. |
| 502 | PuppetDB not reachable or failing. |

Examples:

```bash
curl -u user:pass https://puppetboard.example.com/api/v1/nodes?status=failed
curl -u user:pass https://puppetboard.example.com/api/v1/nodes/web01.example.com/facts?name=os
curl -u user:pass -G https://puppetboard.example.com/api/v1/query --data-urlencode 'pql=nodes[certname] { facts { name = "kernel" and value = "Linux" } }'
```

## MCP server

The MCP server lets AI assistants read your Puppet data: nodes and their
status, facts, reports and catalog resources. It speaks Streamable HTTP on
`/mcp` in stateless JSON mode (no SSE streams, no sessions) and is built on
the official Python MCP SDK.

It only runs when Puppetboard is served through the ASGI entry point, as the
container image does:

```bash
gunicorn -k asgi puppetboard.asgi:app
```

The classic WSGI entry point `puppetboard.app:app` keeps working without MCP.
Outside the container install the package with the `mcp` extra:
`pip install 'puppetboard-dp[mcp]'`.

### MCP settings

| Setting | Docker variable | Default | Meaning |
|---|---|---|---|
| `ENABLE_MCP` | `ENABLE_MCP` | `False` | Serve `/mcp`. |
| `MCP_ALLOWED_HOSTS` | `MCP_ALLOWED_HOSTS` (comma separated) | empty | `Host` headers accepted on `/mcp`, e.g. `puppetboard.example.com`; `host:*` allows any port. Protects against DNS rebinding. Empty refuses every request. |
| `MCP_ALLOWED_ORIGINS` | `MCP_ALLOWED_ORIGINS` (comma separated) | empty | `Origin` headers accepted, e.g. `https://puppetboard.example.com`. Requests without `Origin` (normal MCP clients) are fine. |
| `MCP_MAX_REQUEST_BODY` | `MCP_MAX_REQUEST_BODY` | `65536` | Largest request body in bytes. |
| `MCP_PROTOCOL_VERSIONS` | `MCP_PROTOCOL_VERSIONS` (comma separated) | `2025-06-18,2025-11-25,2026-07-28` | Accepted `MCP-Protocol-Version` headers. |
| `API_RATE_LIMIT` | `API_RATE_LIMIT` | `120` | Same setting as for the API, requests per minute and client, counted separately for `/mcp`. |
| `ENABLE_QUERY` | `ENABLE_QUERY` | `True` | Offers the `run_pql` tool. |
| `ENABLE_CATALOG` | `ENABLE_CATALOG` | `False` | Offers the `list_node_resources` tool. |

### Tools

All tools are read-only and marked so (`readOnlyHint`).

| Tool | What it does |
|---|---|
| `list_environments` | Puppet environments. |
| `list_nodes` | Active nodes with status, filter by `status` and `environment`. |
| `get_node` | Status and timestamps of one node. |
| `search_fact_names` | Top-level fact names containing a substring. |
| `search_fact_paths` | Paths into structured facts matching a regex, with value types. |
| `get_node_facts` | Facts of one node, optionally only some names. |
| `get_fact_values` | One top-level fact on all nodes. |
| `find_fact_values` | Values at a dotted fact path (`*` as wildcard element), optional value regex. |
| `list_node_reports` | Report summaries of a node, newest first. |
| `get_report` | One report with logs, metrics and events. |
| `list_node_resources` | Catalog resources of a node, e.g. type `package`, only with `ENABLE_CATALOG`. |
| `run_pql` | Any PQL query, only with `ENABLE_QUERY`. |

Puppetboard does not add a fact of its own. Facts differ from site to site,
so the server tells the assistant to discover them first (`search_fact_names`,
`search_fact_paths`) and then query values. A question like "which nodes have
openssl 3.0 installed" works if some fact carries package versions, or via
catalog resources of type `package` for packages Puppet manages.

Example client configuration (Claude Code):

```bash
claude mcp add --transport http puppetboard https://puppetboard.example.com/mcp --header "Authorization: Basic $(printf user:pass | base64)"
```

## Securing API and MCP

Puppetboard itself does not authenticate anyone. Both `/api/v1/` and `/mcp`
expose your whole inventory, so:

* Terminate TLS in the reverse proxy and do not expose Puppetboard's own
  plain HTTP port.
* Require authentication in the proxy for `/api/` and `/mcp` (Basic-Auth,
  client certificates or SSO).
* Forward `X-Forwarded-For`/`X-Forwarded-Proto`/`X-Forwarded-Host`: Puppetboard
  trusts exactly one proxy hop for client IPs (rate limit, audit log) and URLs.
* Every API and MCP request is logged by the `puppetboard.audit` logger with
  UTC timestamp, method, path, status, client and duration. Ship these logs to your log
  management.

### CIS benchmark coverage

The API follows the CIS API Security Guide v1.0.0 and the MCP server the CIS
MCP Server Benchmark v1.0.0 where it applies to a read-only, in-app service.
Authentication, authorization and TLS (API guide 1.2, 2.1, 2.2.2, 3.1.4;
MCP benchmark 2.2, 2.3, 3.1, 3.3) are delegated to the reverse proxy by design.

| Rule | How |
|---|---|
| API 1.1 documentation, single source of truth | OpenAPI 3.1 at `/api/v1/openapi.json`, this page. |
| API 2.2.3 request validation | Every path and query parameter is checked against a pattern or range before PuppetDB is asked. |
| API 2.2.4 response control | Paging with an upper bound, PQL results capped at `API_MAX_LIMIT`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`. |
| API 2.2.5 rate limiting | `API_RATE_LIMIT` per client IP. |
| API 2.2.6, 4.1 logging | `puppetboard.audit` log line per request. |
| API 2.3 error handling | One JSON error format, no stack traces or PuppetDB internals (502 hides the cause). |
| API 3.2 versioning | Everything lives under `/api/v1/`. |
| Least privilege | Only `GET`; Puppetboard has no PuppetDB write code path. |

| MCP rule | How |
|---|---|
| 1.1 protocol version pinned and logged | SDK pinned in `requirements-docker.txt`, accepted versions in `MCP_PROTOCOL_VERSIONS`, version in every audit line. |
| 1.2 capability baseline | Tools only, listed above; no resources, prompts, sampling or elicitation. |
| 2.4 MCP headers | `MCP-Protocol-Version` checked against the allow list. |
| 2.5 Origin/Host validation | SDK DNS rebinding protection with `MCP_ALLOWED_HOSTS`/`MCP_ALLOWED_ORIGINS`. |
| 3.2.2 no token passthrough | The server holds no client tokens; PuppetDB is reached with Puppetboard's own settings. |
| 5.1.1 schema validation | Typed tool parameters with patterns and ranges, validated before any PuppetDB call. |
| 5.2.2, 5.2.3 sessions, legacy streams | Stateless mode, JSON responses only, `GET`/`DELETE` refused with 405, no event store. |
| 5.6 side effects | None, every tool is read-only. |
| 6.1 minimal context | Small default limits, trimmed node fields, fact name filter; PuppetDB errors are not passed to the model. |
| 7.1.1 to 7.1.3 audit | One JSON line per request in `puppetboard.audit`: UTC timestamp, client, JSON-RPC method, id, tool, protocol version, status, duration; requests with a null id are refused. |
| 9.1 isolation | Container image without compiler and pip, runs as the unprivileged user `puppetboard` on port 8080. |
| 10.2 limits | Body size limit, rate limit per client, paging bounds. |
