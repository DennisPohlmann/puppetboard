"""Print the CHANGELOG.md section of one version, for the GitHub release notes.

    python .github/scripts/release_notes.py 8.2.1
"""
import re
import sys
from pathlib import Path


def section(changelog, version):
    lines, found = [], False
    for line in changelog.splitlines():
        if line.startswith('## '):
            if found:
                break
            found = line.startswith(f'## [{version}]')
        elif found:
            lines.append(line)
    if not found:
        raise SystemExit(f'CHANGELOG.md has no section for {version}')
    notes = '\n'.join(lines).strip()
    # relative links in CHANGELOG.md would break on the release page
    return re.sub(r'\]\((?!https?:|#)', f'](https://github.com/DennisPohlmann/puppetboard/blob/{version}/', notes)


if __name__ == '__main__':
    print(section((Path(__file__).parents[2] / 'CHANGELOG.md').read_text(), sys.argv[1]))
