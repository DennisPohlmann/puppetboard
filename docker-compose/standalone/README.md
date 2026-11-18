# Puppetboard for an existing PuppetDB

Puppetboard alone, listening on `127.0.0.1:8080`. Put your own reverse proxy
with TLS in front ([Deployment setups](../../docs/Deployment-setups.md)); if
you enable the JSON API or the MCP server, the proxy must also authenticate
clients ([../proxy](../proxy/) shows one).

## PuppetDB certificate

PuppetDB answers remote clients only over TLS with a certificate signed by
the Puppet CA. On the Puppet Server, create one for Puppetboard and allow it
in PuppetDB's `certificate-allowlist`:

```bash
puppetserver ca generate --certname puppetboard.example.com
```

Copy the files into `ssl/` next to `docker-compose.yml`:

| File | From the Puppet Server |
|---|---|
| `ssl/ca.pem` | `/etc/puppetlabs/puppet/ssl/certs/ca.pem` |
| `ssl/cert.pem` | `/etc/puppetlabs/puppet/ssl/certs/puppetboard.example.com.pem` |
| `ssl/key.pem` | `/etc/puppetlabs/puppet/ssl/private_keys/puppetboard.example.com.pem` |

The container user (uid 10001) must be able to read them:

```bash
chmod 0644 ssl/ca.pem ssl/cert.pem
chown 10001 ssl/key.pem && chmod 0400 ssl/key.pem
```

With rootless Podman use `podman unshare chown 10001 ssl/key.pem` instead.

## Settings and start

```bash
cd docker-compose/standalone
cp .env.example .env
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env
```

In `.env` set at least `PUPPETDB_HOST` (the PuppetDB host name from its
certificate) and `PUPPETDB_PORT` (8081 for TLS).

```bash
docker compose up -d        # or: podman-compose up -d
docker compose logs puppetboard
```

Puppetboard is then at http://127.0.0.1:8080/.

## How it is set up

- `docker-compose.yml` sets nothing itself and loads `.env` with `env_file:`.
  The port is published only on 127.0.0.1.
- The root file system is read-only (`/tmp` and the home folder are
  in-memory), all capabilities are dropped, no new privileges.
- `docker-compose.build.yml` builds the image from the checkout instead of
  pulling it.
