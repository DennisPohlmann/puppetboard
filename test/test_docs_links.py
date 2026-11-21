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
