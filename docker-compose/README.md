# docker-compose examples

Puppetboard only: PuppetDB, Puppet Server and the agents are yours, Puppetboard
just connects to an existing PuppetDB with host, port and a client certificate.

| Example | What it runs |
|---|---|
| [standalone](standalone/) | Puppetboard on `127.0.0.1:8080`, for your own reverse proxy |
| [proxy](proxy/) | Puppetboard behind nginx with TLS and Basic-Auth, JSON API and MCP server enabled |

Each folder has a `docker-compose.yml`, an `.env.example` with the settings
(copy it to `.env`) and a README. They work with `docker compose` and
`podman-compose`. The image is `ghcr.io/dennispohlmann/puppetboard`; it runs
as the unprivileged user `puppetboard` (uid 10001) on port 8080 with a
read-only root file system. To build it from the checkout instead:

```bash
docker compose -f docker-compose.yml -f ../standalone/docker-compose.build.yml up -d --build
```

All settings are described in the [docs/Configuration.md](../docs/Configuration.md#app-settings) and,
for API and MCP, in [docs/API.md](../docs/API.md).
