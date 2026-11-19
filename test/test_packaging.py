import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / 'pyproject.toml'


def _names(specs):
    return {spec.split('>')[0].split('<')[0].split('=')[0].strip().lower() for spec in specs}


def test_plain_install_brings_asgi_and_mcp():
    project = tomllib.loads(PYPROJECT.read_text())['project']
    assert {'gunicorn', 'mcp', 'a2wsgi'} <= _names(project['dependencies'])


def test_mcp_extra_kept_as_empty_alias():
    project = tomllib.loads(PYPROJECT.read_text())['project']
    assert project['optional-dependencies']['mcp'] == []
