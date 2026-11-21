# Puppetboard Helm chart

Puppetboard (web interface, read-only JSON API and MCP server) for an
**existing PuppetDB**. The chart ships only Puppetboard; PuppetDB, Puppet
Server and the agents are yours.

Released versions are on ghcr.io as OCI chart, with the same version as the app:

```bash
helm install puppetboard oci://ghcr.io/dennispohlmann/charts/puppetboard --version 9.0.0 \
  --namespace puppetboard --create-namespace \
  --set secretKey="$(openssl rand -hex 32)" \
  --set puppetdb.host=puppetdb.example.com \
  --set puppetdb.tls.existingSecret=puppetboard-puppetdb-tls
helm test puppetboard -n puppetboard
```

The pod runs `ghcr.io/dennispohlmann/puppetboard` as user `puppetboard`
(uid 10001) on port 8080, with a read-only root file system, no
capabilities and no service account token.

## PuppetDB certificate

PuppetDB answers remote clients over TLS with a client certificate signed by
the Puppet CA (allow its certname in PuppetDB's `certificate-allowlist`).
Put it into a Secret with the keys `ca.crt`, `tls.crt` and `tls.key`:

```bash
kubectl -n puppetboard create secret generic puppetboard-puppetdb-tls \
  --from-file=ca.crt=/etc/puppetlabs/puppet/ssl/certs/ca.pem \
  --from-file=tls.crt=/etc/puppetlabs/puppet/ssl/certs/puppetboard.example.com.pem \
  --from-file=tls.key=/etc/puppetlabs/puppet/ssl/private_keys/puppetboard.example.com.pem
```

or pass the PEM texts as `puppetdb.tls.ca`, `.cert` and `.key`. Plain HTTP
(`puppetdb.port: 8080`, `puppetdb.tls.enabled: false`) only inside a
trusted network.

## JSON API and MCP server

Both have **no authentication of their own**. Enable them only behind an
ingress or gateway that authenticates, e.g. Basic-Auth with ingress-nginx:

```yaml
api:
  enabled: true
mcp:
  enabled: true          # allowed hosts default to the ingress/httpRoute hosts
ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: puppetboard-basic-auth
  hosts:
    - host: puppetboard.example.com
      paths: [{path: /, pathType: Prefix}]
  tls:
    - secretName: puppetboard-tls
      hosts: [puppetboard.example.com]
```

```bash
htpasswd -cB auth admin
kubectl -n puppetboard create secret generic puppetboard-basic-auth --from-file=auth
```

Details on the endpoints and the CIS mapping: [docs/API.md](../../docs/API.md), on the MCP tools: [docs/MCP.md](../../docs/MCP.md).

## Values

| Key | Default | Meaning |
|---|---|---|
| `image.registry` / `.repository` / `.tag` / `.digest` | `ghcr.io` / `dennispohlmann/puppetboard` / appVersion / – | Image; a digest wins over the tag. |
| `replicaCount` | `1` | Pods; rate limit and environment cache count per pod. |
| `secretKey` / `existingSecret` | – | Session key (`openssl rand -hex 32`) or a Secret with the key `SECRET_KEY`. One is required. |
| `puppetdb.host` / `.port` | `puppetdb` / `8081` | PuppetDB endpoint. |
| `puppetdb.sslVerify` | `true` | Check PuppetDB's certificate with the CA. |
| `puppetdb.timeout` | `20` | Seconds per PuppetDB request. |
| `puppetdb.tls.enabled` | `true` | Use a client certificate. |
| `puppetdb.tls.existingSecret` | – | Secret with `ca.crt`, `tls.crt`, `tls.key`; or `ca`/`cert`/`key` as PEM text. |
| `api.enabled` / `api.rateLimit` | `false` / `120` | JSON API under `/api/v1/`, requests per minute and client. |
| `api.docs` | `true` | API reference under `/api/v1/docs` (only with `api.enabled`). |
| `mcp.enabled` | `false` | MCP server under `/mcp`. |
| `mcp.allowedHosts` / `.allowedOrigins` | ingress/httpRoute hosts / – | Host and Origin headers accepted on `/mcp`. |
| `config` | see values.yaml | Further settings as environment variables, names as in the [docs/Configuration.md](../../docs/Configuration.md#app-settings). |
| `workers` | `2` | Gunicorn workers per pod. |
| `extraEnv` / `extraEnvFrom` / `extraVolumes` / `extraVolumeMounts` | – | Additions to the pod. |
| `service.type` / `.port` | `ClusterIP` / `80` | Service. |
| `ingress.*` | disabled | Ingress with hosts, TLS and annotations. |
| `httpRoute.*` | disabled | Gateway API HTTPRoute. |
| `networkPolicy.enabled` | `false` | Ingress only on the HTTP port, egress only DNS and PuppetDB. |
| `podDisruptionBudget.enabled` | `false` | PodDisruptionBudget (with `replicaCount` > 1). |
| `podSecurityContext` / `securityContext` | non-root 10001, read-only root, no capabilities | Security contexts. |
| `resources`, `livenessProbe`, `readinessProbe`, `nodeSelector`, `tolerations`, `affinity` | see values.yaml | Scheduling and health. |

`values.schema.json` rejects unknown keys and wrong types. The chart stops at
install with a clear message without a secret key, with TLS but no
certificate, or with MCP but no host name.

## Tests

```bash
helm lint --strict charts/puppetboard -f charts/puppetboard/ci/full-values.yaml
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/charts/puppetboard:/apps" helmunittest/helm-unittest --strict .
```

The CI workflow `chart.yml` runs lint, the unit tests and kubeconform on every
push, and on a release tag pushes the chart to `oci://ghcr.io/dennispohlmann/charts`.
From the checkout, `./charts/puppetboard` works in place of the OCI address.
