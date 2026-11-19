import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('release_notes', ROOT / '.github' / 'scripts' / 'release_notes.py')
assert spec and spec.loader
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [2.0.0](https://example.com/2.0.0) (2026-11-19)

**Fixed**

- second, see [docs/API.md](docs/API.md) and [x](https://example.com/x)

## [1.0.0](https://example.com/1.0.0) (2026-11-18)

- first
"""


def test_section_of_one_version_with_absolute_links():
    notes = release_notes.section(CHANGELOG, '2.0.0')
    assert notes.startswith('**Fixed**') and 'first' not in notes
    assert '](https://github.com/DennisPohlmann/puppetboard/blob/2.0.0/docs/API.md)' in notes
    assert '[x](https://example.com/x)' in notes


def test_last_section_and_missing_version():
    assert release_notes.section(CHANGELOG, '1.0.0') == '- first'
    with pytest.raises(SystemExit):
        release_notes.section(CHANGELOG, '3.0.0')


def test_every_released_version_has_notes():
    text = (ROOT / 'CHANGELOG.md').read_text()
    for version in ('8.2.0', '8.2.1'):
        assert release_notes.section(text, version)
