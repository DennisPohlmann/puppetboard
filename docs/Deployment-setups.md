# Deployment setups

Puppetboard needs a reverse proxy in front: it terminates TLS and, if you use
the JSON API (`/api/v1/`) or the MCP server (`/mcp`), it must authenticate
clients, because Puppetboard has no authentication of its own (see
[API.md](API.md#securing-api-and-mcp)).

Two ways to run it:

- [Container image](#container-image) (recommended), also [managed by Puppet](#managed-by-puppet)
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
environment variables with the names from [Configuration](Configuration.md#app-settings).
The same command works with rootless Podman.

### Managed by Puppet

With the [puppetlabs/docker](https://forge.puppet.com/modules/puppetlabs/docker) module Puppet can run the
container. On the PuppetDB host it reaches PuppetDB's plain HTTP port on
127.0.0.1 and listens on 127.0.0.1:8088 for the reverse proxy:

```puppet
include docker

docker::image { 'ghcr.io/dennispohlmann/puppetboard': }

docker::run { 'puppetboard':
  image => 'ghcr.io/dennispohlmann/puppetboard',
  env   => [
    'PUPPETDB_HOST=127.0.0.1',
    'PUPPETDB_PORT=8080',
    'PUPPETBOARD_HOST=127.0.0.1',
    'PUPPETBOARD_PORT=8088',
    'SECRET_KEY=XXXXXXXX',
  ],
  net   => 'host',
}
```

With TLS to PuppetDB, which a remote PuppetDB requires, the container reads
the agent's own certificate. The key must be readable for the container user
(uid 10001) only:

```puppet
$certname = $trusted['certname']

file { '/etc/puppetboard':
  ensure => directory,
}
file { '/etc/puppetboard/ca.pem':
  ensure => file,
  mode   => '0644',
  source => '/etc/puppetlabs/puppet/ssl/certs/ca.pem',
}
file { '/etc/puppetboard/cert.pem':
  ensure => file,
  mode   => '0644',
  source => "/etc/puppetlabs/puppet/ssl/certs/${certname}.pem",
}
file { '/etc/puppetboard/key.pem':
  ensure => file,
  owner  => 10001,
  mode   => '0400',
  source => "/etc/puppetlabs/puppet/ssl/private_keys/${certname}.pem",
}

include docker

docker::image { 'ghcr.io/dennispohlmann/puppetboard': }

docker::run { 'puppetboard':
  image   => 'ghcr.io/dennispohlmann/puppetboard',
  volumes => ['/etc/puppetboard:/etc/puppetboard:ro'],
  env     => [
    'PUPPETDB_HOST=puppet.example.com', # certname or DNS alt name of the PuppetDB host
    'PUPPETDB_PORT=8081',
    'PUPPETBOARD_HOST=127.0.0.1',
    'PUPPETBOARD_PORT=8088',
    'PUPPETDB_SSL_VERIFY=/etc/puppetboard/ca.pem',
    'PUPPETDB_KEY=/etc/puppetboard/key.pem',
    'PUPPETDB_CERT=/etc/puppetboard/cert.pem',
    'SECRET_KEY=XXXXXXXX',
    'ENABLE_CATALOG=true',
    'DEFAULT_ENVIRONMENT=*',
  ],
  net     => 'host',
}
```

In an air-gapped network add `'OFFLINE_MODE=true'` to `env`, so the browser
loads the JavaScript and fonts from Puppetboard instead of a CDN.

To build the image yourself from a checkout: `docker build -t puppetboard .`

## Python package with gunicorn and systemd

Python 3.12 or newer, e.g. the system Python of RHEL 10:

```bash
python3 -m venv /opt/puppetboard
/opt/puppetboard/bin/pip install puppetboard-dp
useradd --system --user-group --home-dir /opt/puppetboard --shell /sbin/nologin puppetboard
```

`/etc/puppetboard/settings.py` overrides only what differs from
[default_settings.py](../puppetboard/default_settings.py):

```python
PUPPETDB_HOST = 'puppetdb.example.com'
PUPPETDB_PORT = 8081
PUPPETDB_SSL_VERIFY = '/etc/puppetboard/ca.pem'
PUPPETDB_KEY = '/etc/puppetboard/key.pem'
PUPPETDB_CERT = '/etc/puppetboard/cert.pem'
SECRET_KEY = 'change-me-to-a-long-random-string'
ENABLE_API = True
ENABLE_MCP = True
MCP_ALLOWED_HOSTS = ['puppetboard.example.com']
```

`settings.py` holds the `SECRET_KEY` and `key.pem` the private key, so only
root and the group `puppetboard` may read them:

```bash
chgrp puppetboard /etc/puppetboard/settings.py /etc/puppetboard/key.pem
chmod 0640 /etc/puppetboard/settings.py /etc/puppetboard/key.pem
```

`/etc/systemd/system/puppetboard.service`:

```ini
[Unit]
Description=Puppetboard
After=network-online.target
Wants=network-online.target

[Service]
User=puppetboard
Group=puppetboard
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

`puppetboard.asgi:app` is the only entry point and serves the web interface,
the JSON API and the MCP server.

Check it with `systemctl status puppetboard` and `journalctl -u puppetboard`.
gunicorn answers on `127.0.0.1:8080` only; the reverse proxy below is the
way in. After changing `settings.py` or updating the package, run
`systemctl restart puppetboard`.

### SELinux on RHEL

systemd starts a service as `unconfined_service_t` only if its binary is
labelled `bin_t`. pip creates the venv files with the label of the parent
directory, so `/opt/puppetboard/bin` starts out as `usr_t` like the rest of
`/opt`. gunicorn then stays in `init_t` and may neither read its own files
nor connect to PuppetDB. Label the venv from the install above once instead
of building an `audit2allow` module for these denials:

```bash
semanage fcontext -a -t usr_t '/opt/puppetboard(/.*)?'
semanage fcontext -a -t bin_t '/opt/puppetboard/bin(/.*)?'
restorecon -RF /opt/puppetboard
systemctl restart puppetboard
```

A venv elsewhere, e.g. `/srv/puppetboard/virtenv-puppetboard` from the
puppet-puppetboard module, gets `var_t` or keeps `httpd_sys_content_t` from
an earlier Apache mod_wsgi setup: use the same three commands with its path.

Check: `ls -Z <venv>/bin/gunicorn` shows `bin_t` and
`ps -eZ | grep gunicorn` shows `unconfined_service_t`. If an older rule
labels the path differently, `semanage fcontext -l | grep puppetboard`
shows it and `semanage fcontext -d '<path pattern>'` removes it. The
reverse proxy also needs `setsebool -P httpd_can_network_connect 1`.

Under a URL prefix such as `https://example.com/puppetboard/`, add
`--root-path /puppetboard` to gunicorn (container: `PUPPETBOARD_URL_PREFIX`).
All container variables: [Configuration](Configuration.md#container-variables).

## nginx

TLS and Basic-Auth for everything. Puppetboard trusts the `X-Forwarded-*`
headers of exactly one proxy, so put it directly behind this one.
Both examples reach Puppetboard on `127.0.0.1:8080`; for the
[Puppet-managed container](#managed-by-puppet) use port 8088.

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

    # same headers as the nginx block: Host, X-Forwarded-For/-Host (ProxyAddHeaders), -Proto
    ProxyPreserveHost On
    ProxyAddHeaders On
    RequestHeader set X-Forwarded-Proto "https"
    ProxyTimeout 60
    ProxyPass        / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/
</VirtualHost>
```

On RHEL with SELinux, allow the web server to connect to the local port:
`setsebool -P httpd_can_network_connect 1`.
