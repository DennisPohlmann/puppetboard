# Build stage: has pip and a shell, installs everything into a venv.
FROM cgr.dev/chainguard/python:latest-dev AS build
USER root
WORKDIR /usr/src/app
COPY . .
RUN python -m venv /opt/puppetboard \
    && /opt/puppetboard/bin/pip install --no-cache-dir --prefer-binary -r requirements-docker.txt . \
    && /opt/puppetboard/bin/pip uninstall -y pip \
    && addgroup -S -g 10001 puppetboard \
    && adduser -S -D -u 10001 -G puppetboard -h /home/puppetboard -s /sbin/nologin puppetboard

# Runtime stage: Wolfi-based, no shell, no package manager, no pip. Only
# Python and the venv, run as the unprivileged user puppetboard (uid 10001).
FROM cgr.dev/chainguard/python:latest

LABEL org.label-schema.maintainer="Voxpupuli Team <info@voxpupuli.org>" \
      org.label-schema.vendor="Voxpupuli" \
      org.label-schema.url="https://github.com/voxpupuli/puppetboard" \
      org.label-schema.license="Apache-2.0" \
      org.label-schema.vcs-url="https://github.com/voxpupuli/puppetboard" \
      org.label-schema.schema-version="1.0" \
      org.label-schema.dockerfile="/Dockerfile"

ENV PATH=/opt/puppetboard/bin:$PATH \
    PUPPETBOARD_PORT=8080 \
    PUPPETBOARD_HOST=0.0.0.0 \
    PUPPETBOARD_STATUS_ENDPOINT=/status \
    PUPPETBOARD_SETTINGS=docker_settings.py
EXPOSE 8080

COPY --from=build /etc/passwd /etc/group /etc/
COPY --from=build --chown=puppetboard:puppetboard /home/puppetboard /home/puppetboard
COPY --from=build /opt/puppetboard /opt/puppetboard
COPY Dockerfile /

HEALTHCHECK --interval=1m --timeout=5s --start-period=10s CMD ["python", "-m", "puppetboard.healthcheck"]

# ASGI worker: serves the web UI, the JSON API (ENABLE_API) and the MCP server
# (ENABLE_MCP). Port, workers and URL prefix come from the environment, see
# puppetboard/gunicorn_conf.py.
USER puppetboard
ENTRYPOINT ["gunicorn", "-c", "python:puppetboard.gunicorn_conf"]
CMD ["puppetboard.asgi:app"]
