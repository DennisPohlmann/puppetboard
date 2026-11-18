# How to release

Releases of this fork are published as `puppetboard-dp` on PyPI and as
`ghcr.io/dennispohlmann/puppetboard` in the GitHub Container Registry.
A release needs Dennis' explicit "RELEASE GO" and a passed security gate.

1. Set the new version in [pyproject.toml](pyproject.toml), for example with
   `poetry version minor`, and describe the changes in
   [CHANGELOG.md](CHANGELOG.md). Commit both (signed) to `main`.
2. Tag the commit with the plain version, without a `v`, and push the tag:

   ```shell
   git tag -s 8.2.0 -m 'Release 8.2.0'
   git push fork 8.2.0
   ```

The tag starts two workflows:

- `publish-to-pypi.yml` builds the package and uploads it to PyPI with
  Trusted Publishing (environment `pypi`, no API token), then creates the
  GitHub release.
- `publish-docker.yml` builds the image for amd64 and arm64 and pushes
  `ghcr.io/dennispohlmann/puppetboard:<version>` and `:latest`.
