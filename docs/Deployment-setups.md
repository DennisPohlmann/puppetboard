# Deployment setups

Puppetboard needs a reverse proxy in front: it terminates TLS and, if you use
the JSON API (`/api/v1/`) or the MCP server (`/mcp`), it must authenticate
clients, because Puppetboard has no authentication of its own (see
[API.md](API.md#securing-api-and-mcp)).

Two ways to run it:

- [Container image](#container-image) (recommended)
- [Python package with gunicorn and systemd](#python-package-with-gunicorn-and-systemd)

Then put [nginx](#nginx) or [Apache](#apache) in front.

## Container image

```bash
docker run -d --name puppetboard --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -e PUPPETDB_HOST=puppetdb.example.com -e PUPPETDB_PORT=8081 \
  -e PUPPETDB_SSL_VERIFY=/etc/puppetboard/ca.pem \
  -e PUPPETDB_KEY=/etc/puppetboard/key.pem -e PUPPETDB_CERT=/etc/puppetboard/cert.pem \
  -e SECRET_KEY=change-me-to-a-long-random-string \
  -e ENABLE_API=true -e ENABLE_MCP=true -e MCP_ALLOWED_HOSTS=puppetboard.example.com \
  -v /etc/puppetboard:/etc/puppetboard:ro \
  ghcr.io/dennispohlmann/puppetboard
```

The image runs as user `puppetboard` (uid 10001) on port 8080; the key and
certificate files must be readable for that user. All settings are
environment variables with the names from the [README](../README.md#app-settings).
The same command works with rootless Podman.

## Python package with gunicorn and systemd

Python 3.12 or newer, e.g. the system Python of RHEL 10:

```bash
python3 -m venv /opt/puppetboard
/opt/puppetboard/bin/pip install 'puppetboard-dp[mcp]'
useradd --system --home-dir /opt/puppetboard --shell /sbin/nologin puppetboard
```

`/etc/puppetboard/settings.py` overrides only what differs from
[default_settings.py](../puppetboard/default_settings.py):

```python
PUPPETDB_HOST = 'puppetdb.example.com'
PUPPETDB_PORT = 8081
PUPPETDB_SSL_VERIFY = '/etc/puppetlabs/puppet/ssl/certs/ca.pem'
PUPPETDB_KEY = '/etc/puppetboard/key.pem'
PUPPETDB_CERT = '/etc/puppetboard/cert.pem'
SECRET_KEY = 'change-me-to-a-long-random-string'
ENABLE_API = True
ENABLE_MCP = True
MCP_ALLOWED_HOSTS = ['puppetboard.example.com']
```

`/etc/systemd/system/puppetboard.service`:

```ini
[Unit]
Description=Puppetboard
After=network-online.target
Wants=network-online.target

[Service]
User=puppetboard
Environment=PUPPETBOARD_SETTINGS=/etc/puppetboard/settings.py
ExecStart=/opt/puppetboard/bin/gunicorn -k asgi --workers 2 -b 127.0.0.1:8080 puppetboard.asgi:app
Restart=on-failure
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now puppetboard
```

`puppetboard.asgi:app` serves the web interface, the JSON API and the MCP
server. If you need neither MCP nor ASGI, the WSGI app `puppetboard.app:app`
runs with any WSGI server, e.g. `gunicorn puppetboard.app:app`.

Under a URL prefix such as `https://example.com/puppetboard/`, add
`--root-path /puppetboard` to gunicorn (container: `PUPPETBOARD_URL_PREFIX`).

## nginx

TLS and Basic-Auth for everything. Puppetboard trusts the `X-Forwarded-*`
headers of exactly one proxy, so put it directly behind this one.

```nginx
server {
    listen 443 ssl;
    server_name puppetboard.example.com;
    ssl_certificate     /etc/pki/tls/certs/puppetboard.crt;
    ssl_certificate_key /etc/pki/tls/private/puppetboard.key;

    auth_basic           "Puppetboard";
    auth_basic_user_file /etc/nginx/puppetboard.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_read_timeout 60s;
    }
}
```

## Apache

```apache
<VirtualHost *:443>
    ServerName puppetboard.example.com
    SSLEngine on
    SSLCertificateFile    /etc/pki/tls/certs/puppetboard.crt
    SSLCertificateKeyFile /etc/pki/tls/private/puppetboard.key

    <Location "/">
        AuthType Basic
        AuthName "Puppetboard"
        AuthBasicProvider file
        AuthUserFile /etc/httpd/puppetboard.htpasswd
        Require valid-user
    </Location>

    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    ProxyPass        / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/
</VirtualHost>
```

On RHEL with SELinux, allow the web server to connect to the local port:
`setsebool -P httpd_can_network_connect 1`.
