# Development

Puppetboard is a [Flask](https://flask.palletsprojects.com) application that
reads PuppetDB through [pypuppetdb](https://pypi.org/project/pypuppetdb/).
`puppetboard/asgi.py` wraps it for gunicorn's ASGI worker and adds the MCP
server; the JSON API is a Flask blueprint in `puppetboard/views/api.py`.

## Set up

Python 3.12 is the oldest supported version (RHEL 10); CI tests 3.12 to 3.15.

```bash
git clone git@github.com:DennisPohlmann/puppetboard.git
cd puppetboard
python3 -m venv venv
. venv/bin/activate
pip install -r requirements-test.txt -e .
```

Dependency versions are pinned only in the `requirements*.txt` files.

## Run

You need a PuppetDB to talk to. Put the settings that differ from
`puppetboard/default_settings.py` into `settings.py`, then:

```bash
export PUPPETBOARD_SETTINGS=$PWD/settings.py
gunicorn -k asgi --reload -b 127.0.0.1:5000 puppetboard.asgi:app
```

`--reload` restarts the app when a file changes.

## Tests

The same checks as the CI workflow `tests.yml`:

```bash
pytest --cov=. --cov-report=xml --strict-markers --mypy puppetboard test
pylint --errors-only puppetboard test
bandit -r puppetboard
```

Every change comes with matching unit tests. The tests need no PuppetDB; they
mock it. `test/test_docs_links.py` checks that the relative links in the
documentation resolve, `test/test_packaging.py` guards packaging and
dependency pins. Tests for the Helm chart: [charts/puppetboard](../charts/puppetboard/README.md#tests).

## Commits

One change per commit, signed, with a message that says what changed and why,
not "fixed typo". See [this post by Tim Pope](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html)
for the format.

## Releases

See [RELEASE.md](../RELEASE.md).
