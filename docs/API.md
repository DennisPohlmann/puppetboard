# JSON API

Puppetboard can serve a read-only JSON API under `/api/v1/`. It reads the
same PuppetDB data as the web interface and never writes to PuppetDB.

The API has **no authentication of its own**. Run it behind a reverse proxy
that terminates TLS and authenticates clients (for example HTTP Basic-Auth),
see [Securing API and MCP](#securing-api-and-mcp).

## Settings

| Setting | Docker variable | Default | Meaning |
|---|---|---|---|
| `ENABLE_API` | `ENABLE_API` | `False` | Serve `/api/v1/`. When off every API URL answers 404. |
| `API_DEFAULT_LIMIT` | `API_DEFAULT_LIMIT` | `100` | Page size when `limit` is not given. |
| `API_MAX_LIMIT` | `API_MAX_LIMIT` | `1000` | Largest allowed `limit`, also caps PQL results. |
| `API_MAX_QUERY_LENGTH` | `API_MAX_QUERY_LENGTH` | `4096` | Longest accepted PQL query. |
| `API_RATE_LIMIT` | `API_RATE_LIMIT` | `120` | Requests per minute and client IP (API and MCP), `0` turns it off. Counted per worker process. |
| `ENABLE_QUERY` | `ENABLE_QUERY` | `True` | Also gates `/api/v1/query` (and `ENABLED_QUERY_ENDPOINTS` must contain `pql`). |

## Endpoints

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
| `/api/v1/nodes/<certname>/resources?type=&title=` | Catalog resources of the node, e.g. `type=package`. |
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
| 403 | PQL query while `ENABLE_QUERY` is off. |
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
  method, path, status, client and duration. Ship these logs to your log
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
