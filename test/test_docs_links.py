import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md')),
        *sorted((ROOT / 'docker-compose').rglob('README.md')), ROOT / 'charts' / 'puppetboard' / 'README.md']
LINK = re.compile(r'\]\(([^)\s]+)\)|<img src="([^"]+)"')


def _anchors(md):
    # GitHub heading ids: lower case, punctuation dropped, spaces to dashes
    text = re.sub(r'```.*?```', '', md.read_text(), flags=re.S)
    return {re.sub(r'[^\w\- ]', '', h.strip().lower()).replace(' ', '-') for h in re.findall(r'^#+ (.+)$', text, re.M)}


@pytest.mark.parametrize('doc', DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(doc):
    for match in LINK.finditer(doc.read_text()):
        target = match.group(1) or match.group(2)
        if re.match(r'[a-z]+:', target):
            continue
        path, _, anchor = target.partition('#')
        dest = (doc.parent / path).resolve() if path else doc
        assert dest.exists(), f'{doc}: {target}'
        if anchor and dest.suffix == '.md':
            assert anchor in _anchors(dest), f'{doc}: {target}'


def test_readme_images_are_absolute_for_pypi():
    # PyPI shows README.md without the repository, so relative images break there
    for match in re.finditer(r'!\[[^\]]*\]\(([^)\s]+)\)|<img src="([^"]+)"', (ROOT / 'README.md').read_text()):
        assert (match.group(1) or match.group(2)).startswith('https://'), match.group(0)


def test_systemd_unit_sets_user_and_group():
    # the unit runs as puppetboard:puppetboard, so the documented useradd must create that group
    doc = (ROOT / 'docs' / 'Deployment-setups.md').read_text()
    assert re.search(r'^User=puppetboard\nGroup=puppetboard$', doc, re.M)
    assert re.search(r'^useradd --system --user-group .* puppetboard$', doc, re.M)


def test_apache_proxy_matches_nginx_headers():
    # nginx sets Host, X-Forwarded-For/-Proto/-Host and a 60 s timeout; Apache must send the same
    apache = (ROOT / 'docs' / 'Deployment-setups.md').read_text().split('```apache', 1)[1].split('```', 1)[0]
    for line in ('ProxyPreserveHost On', 'ProxyAddHeaders On', 'RequestHeader set X-Forwarded-Proto "https"',
                 'ProxyTimeout 60'):
        assert line in apache, line


def test_systemd_install_unit_and_selinux_use_the_same_venv():
    # install, unit and SELinux labels drifted apart once (/opt vs /srv); keep them on one venv path
    doc = (ROOT / 'docs' / 'Deployment-setups.md').read_text()
    section = doc.split('## Python package with gunicorn and systemd', 1)[1].split('\n## ', 1)[0]
    venv = re.search(r'^python3 -m venv (\S+)$', section, re.M).group(1)
    assert re.search(rf'^ExecStart={re.escape(venv)}/bin/gunicorn ', section, re.M)
    assert f"semanage fcontext -a -t usr_t '{venv}(/.*)?'" in section
    assert f"semanage fcontext -a -t bin_t '{venv}/bin(/.*)?'" in section
    assert f'restorecon -RF {venv}\n' in section


def test_systemd_setup_files_are_readable_for_the_service_group():
    # the unit runs as group puppetboard: settings.py and the key must be readable for it, nobody else
    doc = (ROOT / 'docs' / 'Deployment-setups.md').read_text()
    section = doc.split('## Python package with gunicorn and systemd', 1)[1].split('\n## ', 1)[0]
    paths = re.findall(r"^PUPPETDB_(?:SSL_VERIFY|KEY|CERT) = '([^']+)'$", section, re.M)
    assert len(paths) == 3 and all(p.startswith('/etc/puppetboard/') for p in paths), paths
    assert 'chgrp puppetboard /etc/puppetboard/settings.py /etc/puppetboard/key.pem\n' in section
    assert 'chmod 0640 /etc/puppetboard/settings.py /etc/puppetboard/key.pem\n' in section
