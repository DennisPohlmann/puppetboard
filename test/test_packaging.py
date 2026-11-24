import base64
import hashlib
import re
import tomllib

import pytest
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / 'pyproject.toml'


def _names(specs):
    return {spec.split('>')[0].split('<')[0].split('=')[0].strip().lower() for spec in specs}


def test_plain_install_brings_asgi_and_mcp():
    project = tomllib.loads(PYPROJECT.read_text())['project']
    assert {'gunicorn', 'mcp', 'a2wsgi'} <= _names(project['dependencies'])


def test_gunicorn_floor_has_the_asgi_worker():
    # '-k asgi' exists since gunicorn 24.0; an older one cannot serve puppetboard.asgi:app
    deps = tomllib.loads(PYPROJECT.read_text())['project']['dependencies']
    assert any(dep.replace(' ', '').startswith('gunicorn>=24') for dep in deps)


def test_mcp_extra_kept_as_empty_alias():
    project = tomllib.loads(PYPROJECT.read_text())['project']
    assert project['optional-dependencies']['mcp'] == []


def test_docs_name_only_the_asgi_entry_point():
    root = PYPROJECT.parent
    docs = [p for p in root.rglob('*.md') if p.name != 'CHANGELOG.md' and not {'venv', '.venv', 'node_modules', 'dist'} & set(p.parts)]
    for doc in docs:
        text = doc.read_text()
        assert 'puppetboard.app:app' not in text, doc
        assert 'flask --app' not in text, doc


@pytest.mark.parametrize('name', ['wsgi.py', 'HISTORY.md', 'settings.py.sample', '.pre-commit-config.yaml', 'poetry.lock', 'setup.cfg'])
def test_removed_leftover_files_stay_gone(name):
    assert not (PYPROJECT.parent / name).exists()


def test_dropped_test_dependencies_stay_out():
    pins = {line.split('==')[0].strip() for line in (PYPROJECT.parent / 'requirements-test.txt').read_text().splitlines()}
    for name in ('pep8', 'cov-core', 'mock', 'types-toml', 'types-setuptools', 'pytest-pylint'):
        assert name not in pins, name


def test_requirements_files_are_the_only_dependency_pins():
    assert 'group' not in tomllib.loads(PYPROJECT.read_text())['tool']['poetry']
    for workflow in (PYPROJECT.parent / '.github' / 'workflows').glob('*.yml'):
        assert 'poetry' not in workflow.read_text(), workflow


def test_workflows_do_not_trigger_on_master():
    for workflow in (PYPROJECT.parent / '.github' / 'workflows').glob('*.yml'):
        assert '- master' not in workflow.read_text(), workflow


def test_vendored_scalar_matches_third_party_version():
    root = PYPROJECT.parent
    row = next(line for line in (root / 'THIRD_PARTY.md').read_text().splitlines() if 'libs/scalar/' in line)
    version = row.split('|')[2].strip()
    bundle = (root / 'puppetboard' / 'static' / 'libs' / 'scalar' / 'standalone.js').read_text()
    assert f'@scalar/api-reference@{version}`' in bundle


def test_offline_libs_match_their_integrity_hashes():
    # a lib update that forgets the SRI hash breaks the page silently in the browser
    static = PYPROJECT.parent / 'puppetboard' / 'static'
    offline = (PYPROJECT.parent / 'puppetboard' / 'templates' / '_static_offline.html').read_text()
    pairs = re.findall(r"filename='(libs/[^']+)'\) ?}}[\"'] +integrity=\"(sha512-[^\"]+)\"", offline)
    assert len(pairs) == 13
    for path, sri in pairs:
        digest = base64.b64encode(hashlib.sha512((static / path).read_bytes()).digest()).decode()
        assert sri == f'sha512-{digest}', path


def test_online_and_offline_libs_use_the_same_files():
    templates = PYPROJECT.parent / 'puppetboard' / 'templates'
    online = set(re.findall(r'integrity="(sha512-[^"]+)"', (templates / '_static_online.html').read_text()))
    offline = set(re.findall(r'integrity="(sha512-[^"]+)"', (templates / '_static_offline.html').read_text()))
    assert online == offline


@pytest.mark.parametrize('component, path', [
    ('DataTables', 'datatables.net/dataTables.min.js'),
    ('DataTables Buttons', 'datatables.net-buttons/dataTables.buttons.min.js'),
])
def test_vendored_datatables_match_third_party_version(component, path):
    root = PYPROJECT.parent
    row = next(line for line in (root / 'THIRD_PARTY.md').read_text().splitlines()
               if line.startswith(f'| {component} |'))
    version = row.split('|')[2].strip()
    assert f' {version}' in (root / 'puppetboard' / 'static' / 'libs' / path).read_text()[:200]
    assert f'/{path.split("/")[0]}/{version}/' in (root / 'puppetboard' / 'templates' / '_static_online.html').read_text()
