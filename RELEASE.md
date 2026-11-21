# How to release

Releases of this fork are published as `puppetboard-dp` on PyPI and as
`ghcr.io/dennispohlmann/puppetboard` in the GitHub Container Registry.
A release needs Dennis' explicit "RELEASE GO" and a passed security gate.

1. Set the new version in [pyproject.toml](pyproject.toml), in `version` and `appVersion` of
   [charts/puppetboard/Chart.yaml](charts/puppetboard/Chart.yaml), in the image tag of
   `charts/puppetboard/tests/deployment_test.yaml` and in the `--version` of the chart README. Turn
   "Unreleased" in [CHANGELOG.md](CHANGELOG.md) into the version's section. Commit (signed) to `main`.
2. Tag the commit with the plain version, without a `v`, and push the tag:

   ```shell
   git tag -s 8.2.0 -m 'Release 8.2.0'
   git push fork 8.2.0
   ```

The tag starts three workflows. Each first checks that the tagged commit is
on `main` and that the tag matches the version in `pyproject.toml`, and stops
otherwise:

- `publish-to-pypi.yml` checks that the tag matches the version in
  `pyproject.toml`, runs the unit tests, builds the package and uploads it to PyPI with
  Trusted Publishing (environment `pypi`, no API token), then creates the
  GitHub release. Its notes are the version's section of `CHANGELOG.md`
  followed by the "Full Changelog" link; without that section the workflow
  stops before publishing.
- `publish-docker.yml` builds the image for amd64 and arm64 and pushes
  `ghcr.io/dennispohlmann/puppetboard:<version>` and `:latest`.
- `chart.yml` checks the Helm chart and pushes it with the tag as chart and
  app version to `oci://ghcr.io/dennispohlmann/charts/puppetboard`.
