# Build stage: has pip and a shell, installs everything into a venv.
FROM cgr.dev/chainguard/python:latest-dev AS build
USER root
WORKDIR /usr/src/app
COPY . .
RUN python -m venv /opt/puppetboard \
    && /opt/puppetboard/bin/pip install --no-cache-dir --prefer-binary -r requirements-docker.txt . \
    && /opt/puppetboard/bin/pip uninstall -y pip

# Runtime stage: Wolfi-based, no shell, no package manager, no pip, runs as
# nonroot. Only Python and the venv, which keeps the scanner findings at zero.
FROM cgr.dev/chainguard/python:latest

LABEL org.label-schema.maintainer="Voxpupuli Team <info@voxpupuli.org>" \
      org.label-schema.vendor="Voxpupuli" \
      org.label-schema.url="https://github.com/voxpupuli/puppetboard" \
      org.label-schema.license="Apache-2.0" \
      org.label-schema.vcs-url="https://github.com/voxpupuli/puppetboard" \
      org.label-schema.schema-version="1.0" \
      org.label-schema.dockerfile="/Dockerfile"

ENV PATH=/opt/puppetboard/bin:$PATH \
    PUPPETBOARD_PORT=80 \
    PUPPETBOARD_HOST=0.0.0.0 \
    PUPPETBOARD_STATUS_ENDPOINT=/status \
    PUPPETBOARD_SETTINGS=docker_settings.py
EXPOSE 80

COPY --from=build /opt/puppetboard /opt/puppetboard
COPY Dockerfile /

HEALTHCHECK --interval=1m --timeout=5s --start-period=10s CMD ["python", "-m", "puppetboard.healthcheck"]

# ASGI worker: serves the web UI, the JSON API (ENABLE_API) and the MCP server
# (ENABLE_MCP). Port, workers and URL prefix come from the environment, see
# puppetboard/gunicorn_conf.py.
ENTRYPOINT ["gunicorn", "-c", "python:puppetboard.gunicorn_conf"]
CMD ["puppetboard.asgi:app"]
