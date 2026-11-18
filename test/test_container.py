import importlib

from puppetboard import healthcheck


def test_gunicorn_conf_from_env(monkeypatch):
    monkeypatch.setenv('PUPPETBOARD_HOST', '127.0.0.1')
    monkeypatch.setenv('PUPPETBOARD_PORT', '8080')
    monkeypatch.setenv('PUPPETBOARD_WORKERS', '3')
    monkeypatch.setenv('PUPPETBOARD_URL_PREFIX', '/pb')
    from puppetboard import gunicorn_conf
    conf = importlib.reload(gunicorn_conf)
    assert (conf.bind, conf.workers, conf.root_path, conf.worker_class) == \
        ('127.0.0.1:8080', 3, '/pb', 'asgi')


def test_gunicorn_conf_defaults(monkeypatch):
    for name in ('PUPPETBOARD_HOST', 'PUPPETBOARD_PORT', 'PUPPETBOARD_WORKERS',
                 'PUPPETBOARD_URL_PREFIX'):
        monkeypatch.delenv(name, raising=False)
    from puppetboard import gunicorn_conf
    conf = importlib.reload(gunicorn_conf)
    assert (conf.bind, conf.workers, conf.root_path) == ('0.0.0.0:8080', 1, '')


def test_healthcheck_url(monkeypatch):
    monkeypatch.setenv('PUPPETBOARD_PORT', '8080')
    monkeypatch.setenv('PUPPETBOARD_URL_PREFIX', '/pb')
    monkeypatch.delenv('PUPPETBOARD_STATUS_ENDPOINT', raising=False)
    assert healthcheck.url() == 'http://localhost:8080/pb/status'


def test_healthcheck_unreachable(monkeypatch):
    monkeypatch.setenv('PUPPETBOARD_PORT', '1')
    assert healthcheck.main() == 1
