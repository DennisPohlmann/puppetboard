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


def test_docs_name_only_the_asgi_entry_point():
    root = PYPROJECT.parent
    docs = [root / 'README.md', *sorted((root / 'docs').glob('*.md'))]
    for doc in docs:
        text = doc.read_text()
        assert 'puppetboard.app:app' not in text, doc
        assert 'flask --app' not in text, doc


def test_no_wsgi_entry_file():
    assert not (PYPROJECT.parent / 'wsgi.py').exists()


def test_dropped_test_dependencies_stay_out():
    pins = {line.split('==')[0].strip() for line in (PYPROJECT.parent / 'requirements-test.txt').read_text().splitlines()}
    group = tomllib.loads(PYPROJECT.read_text())['tool']['poetry']['group']['test']['dependencies']
    for name in ('pep8', 'cov-core', 'mock', 'types-toml', 'types-setuptools', 'pytest-pylint'):
        assert name not in pins and name not in group, name
