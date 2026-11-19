# Development

Puppetboard relies on the [pypuppetdb](https://pypi.org/project/pypuppetdb/) library to fetch data from PuppetDB
and is built with the help of the [Flask](https://flask.palletsprojects.com) microframework.

The recommended way to hack on Puppetboard is to:
1. clone the GitHub repository;
2. create a virtual environment;
```bash
$ python3 -m venv venv
$ . venv/bin/activate # run `deactivate` to exit the virtual environment
```
3. install the package and the test requirements.
```bash
$ pip install -r requirements-test.txt -e .
```

You can then run the tests with:
```bash
pytest --cov=. --cov-report=xml --strict-markers --mypy puppetboard test
pylint --errors-only puppetboard test
```

And you can run the app by executing:

```bash
$ export PUPPETBOARD_SETTINGS=$PWD/settings.py # overrides for puppetboard/default_settings.py
$ gunicorn -k asgi --reload -b 127.0.0.1:5000 puppetboard.asgi:app
```

`--reload` restarts the app when a file changes. Every change comes with matching unit tests.

## Commit messages

Write decent commit messages. Don't use swear words and refrain from uninformative commit messages as 'fixed typo'.

The preferred format of a commit message:

    Fixed a typo in the Nodes section.

    If needed, elaborate further on this commit. Feel free to write a
    complete blog post here if that helps us understand what this is
    all about.

    Fixes #4 and resolves #2.

If you'd like a more elaborate guide on how to write and format your commit messages have a look at [this post
by Tim Pope](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html).

## Build a release

See [RELEASE.md](../RELEASE.md).
