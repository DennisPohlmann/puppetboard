# Configuration

Outside the container Puppetboard reads a Python file named by the
environment variable `PUPPETBOARD_SETTINGS`. The container image, the Helm
chart and the Compose examples take the same names as environment variables.
How to run it: [Deployment setups](Deployment-setups.md).

## Puppet agents

With the agent default `usecacheonfailure = true`, a run whose catalog fails
to compile (for example because of a syntax error) falls back to the last
cached catalog and is reported to PuppetDB as successful; the error only shows
in the run's log. To see such nodes as failed in Puppetboard, set
`usecacheonfailure = false` in the agents' `puppet.conf`.

## PuppetDB

The Puppet Server must store its reports in PuppetDB, see the
[PuppetDB documentation](https://puppet.com/docs/puppetdb/latest/connect_puppet_server.html).

Puppetboard on another host than PuppetDB connects over TLS with a client
certificate signed by the Puppet CA. Allow its certname in PuppetDB's
[certificate allowlist](https://puppet.com/docs/puppetdb/latest/configure.html#certificate-allowlist).
How to create the certificate: [pypuppetdb documentation](https://pypuppetdb.readthedocs.io/en/latest/connecting.html#ssl).

## App settings

The settings file overrides only what differs from
[default_settings.py](../puppetboard/default_settings.py). On the PuppetDB host
the defaults are enough; elsewhere set at least the connection and always a
`SECRET_KEY`:

```python
PUPPETDB_HOST = 'puppetdb.example.com'
PUPPETDB_PORT = 8081
PUPPETDB_SSL_VERIFY = '/etc/puppetboard/ca.pem'
PUPPETDB_KEY = '/etc/puppetboard/key.pem'
PUPPETDB_CERT = '/etc/puppetboard/cert.pem'
SECRET_KEY = 'output of: openssl rand -hex 32'
```

### PuppetDB connection

| Setting | Default | Meaning |
|---|---|---|
| `PUPPETDB_HOST` | `localhost` (container: `puppetdb`) | PuppetDB host name; with TLS the name in its certificate. |
| `PUPPETDB_PORT` | `8080` | `8080` plain HTTP on the PuppetDB host, `8081` TLS. |
| `PUPPETDB_PROTO` | `None` | `http` or `https`; by default derived from the certificate settings. |
| `PUPPETDB_SSL_VERIFY` | `True` | `True`, `False` or the path to the Puppet CA certificate. |
| `PUPPETDB_KEY` / `PUPPETDB_CERT` | `None` | Client key and certificate (path). |
| `PUPPETDB_TIMEOUT` | `20` | Seconds per PuppetDB request; raise it for large results. |

### General

| Setting | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | empty | Session key, required. A long random string, the same on every replica, kept secret. |
| `PAGE_TITLE` | `Puppetboard` | Title of the browser window. |
| `DEFAULT_ENVIRONMENT` | `production` | Environment shown first; `*` for all environments. |
| `FAVORITE_ENVS` | `production`, `staging`, `qa`, `test`, `dev` (container: without `test`) | Environments listed right after "All Environments" in the selector; unknown names are ignored. |
| `UNRESPONSIVE_HOURS` | `2` | Hours without a report after which a node counts as unreported. |
| `REFRESH_RATE` | `30` | Seconds until the overview reloads itself. |
| `OVERVIEW_FILTER` | `None` | Extra PuppetDB query (pypuppetdb QueryBuilder) for the nodes on the overview. |
| `OFFLINE_MODE` | `False` | Serve jQuery, Fomantic-UI, DataTables and the fonts from Puppetboard instead of a CDN, for air-gapped networks. |
| `LOCALISE_TIMESTAMP` | `True` | Show times in the browser's time zone; otherwise UTC. |
| `LOGLEVEL` | `info` | `debug`, `info`, `warning`, `error` or `critical`. |

### Lists and pages

| Setting | Default | Meaning |
|---|---|---|
| `NORMAL_TABLE_COUNT` | `100` | Rows of the node and report lists (container: `REPORTS_COUNT`). |
| `LITTLE_TABLE_COUNT` | `10` | Reports shown on a node page. |
| `TABLE_COUNT_SELECTOR` | `10, 20, 50, 100, 500` | Choices for rows per page. |
| `WITH_EVENT_NUMBERS` | `True` | Show the number of changed resources per node; `False` is faster with several hundred nodes. |
| `DISPLAYED_METRICS` | `resources.total`, `events.failure`, `events.success`, `resources.skipped`, `events.noop` | Report metrics shown in the node summary. |
| `DAILY_REPORTS_CHART_ENABLED` | `True` | Daily chart of report results on the overview and node pages. |
| `DAILY_REPORTS_CHART_DAYS` | `8` | Days in that chart. |
| `DAILY_REPORTS_CHART_MODE` | `stacked` | `stacked` or `split`. |
| `SHOW_ERROR_AS` | `friendly` | `friendly` shortens Puppet errors on the report and failures pages, `raw` shows them unchanged. |
| `CODE_PREFIX_TO_REMOVE` | `/etc/puppetlabs/code/environments(/.*?/modules)?` (container: without the modules part) | Regex of the code path that friendly errors shorten to `…`. |

### Facts and inventory

| Setting | Default | Meaning |
|---|---|---|
| `GRAPH_FACTS` | `architecture`, `clientversion`, `domain`, `osfamily`, `puppetversion`, … | Facts that get a chart on their fact page. Unique or structured facts make poor charts. |
| `GRAPH_TYPE` | `pie` | `pie` or `donut` ([billboard.js](https://naver.github.io/billboard.js/demo/)). |
| `INVENTORY_FACTS` | Hostname, IP Address, OS, Architecture, Kernel Version, Puppet Version | Columns of the inventory page as `(header, fact)` pairs; a dotted name reads into a structured fact. Missing facts show `undef`. |
| `INVENTORY_FACT_TEMPLATES` | links `trusted` to the node, formats `os` | Jinja template per fact name for the inventory cells. |

### Query, catalog, API and MCP

| Setting | Default | Meaning |
|---|---|---|
| `ENABLE_QUERY` | `True` | Query page, `/api/v1/query` and the MCP tool `run_pql`. PQL reads every PuppetDB entity, catalogs and resource parameters included, also with `ENABLE_CATALOG` off. Turn it off if your catalogs hold secrets. |
| `ENABLED_QUERY_ENDPOINTS` | all | PuppetDB endpoints the Query page may use, e.g. `['facts', 'nodes']`; names in `QUERY_ENDPOINTS` of `puppetboard/forms.py`. Not available in the container. |
| `QUERY_PRESETS_FILE` | `None` | YAML file with saved queries for the Query page, see [QUERY_PRESETS.md](../QUERY_PRESETS.md). |
| `ENABLE_CATALOG` | `False` | Catalog of a node (resources, files, relationships), also catalog resources in API and MCP. |
| `ENABLE_API` | `False` | Read-only JSON API under `/api/v1/`; its `API_*` settings are in [API.md](API.md#api-settings). |
| `ENABLE_MCP` | `False` | Read-only MCP server under `/mcp`, needs `MCP_ALLOWED_HOSTS`; its `MCP_*` settings are in [MCP.md](MCP.md#mcp-settings). |

### Classes view

The classes page groups the resource events of the latest reports by Puppet
class. Parsing all reports is slow, so a background job fills a cache.

| Setting | Default | Meaning |
|---|---|---|
| `ENABLE_CLASS` | `False` | Classes page. |
| `CLASS_EVENTS_STATUS_COLUMNS` | `failure`, `success`, `noop` | Event statuses shown as columns, as `(status, header)` pairs. |
| `SCHEDULER_ENABLED` | `False` | Run the background jobs of `SCHEDULER_JOBS`. |
| `SCHEDULER_JOBS` | cache job every 300 seconds | Jobs with `id`, `func`, `trigger` (`interval`) and `seconds`. |
| `SCHEDULER_LOCK_BIND_PORT` | `49100` | Free local port that makes only one worker run the jobs. Not available in the container. |
| `CACHE_TYPE` | `SimpleCache` | `SimpleCache` keeps the cache per process; with more than one worker use a shared one such as `MemcachedCache`. |
| `CACHE_MEMCACHED_SERVERS` | `memcached:11211` (container) | Memcached servers for `MemcachedCache`. |
| `CACHE_DEFAULT_TIMEOUT` | `3600` | Cache lifetime in seconds. |

## Container variables

The image reads the settings above from environment variables of the same
name, with these rules:

- Booleans: `true`/`false`, also `yes`/`no`, `1`/`0`.
- Lists are comma separated: `FAVORITE_ENVS=production,staging`.
- Pairs are flattened: `INVENTORY_FACTS=Hostname,trusted,OS,os.name` and
  `CLASS_EVENTS_STATUS_COLUMNS=failure,Failure,noop,Noop`.
- `SCHEDULER_JOBS` is `id,<id>,func,<func>,trigger,interval,seconds,<n>`,
  several jobs separated by `;`.
- `INVENTORY_FACT_TEMPLATES` is a JSON object.
- `PUPPETDB_SSL_VERIFY`, `PUPPETDB_KEY` and `PUPPETDB_CERT` take a path or the
  PEM text itself, plain or base64 encoded, e.g. from a secret store:

  ```
  PUPPETDB_CERT="-----BEGIN CERTIFICATE-----
  ...
  -----END CERTIFICATE-----"
  ```

Only in the container:

| Variable | Default | Meaning |
|---|---|---|
| `PUPPETBOARD_HOST` | `0.0.0.0` | Address gunicorn listens on. |
| `PUPPETBOARD_PORT` | `8080` | Port gunicorn listens on; with `--net=host` next to PuppetDB pick another one. |
| `PUPPETBOARD_WORKERS` | `1` | gunicorn workers. |
| `PUPPETBOARD_URL_PREFIX` | empty | Path when served below a prefix, e.g. `/puppetboard`. |
| `PUPPETBOARD_STATUS_ENDPOINT` | `/status` | Path the health check calls. |
| `REPORTS_COUNT` | `100` | Sets `NORMAL_TABLE_COUNT`. |
