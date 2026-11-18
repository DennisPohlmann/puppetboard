FROM python:3.15.2-alpine

LABEL org.label-schema.maintainer="Voxpupuli Team <info@voxpupuli.org>" \
      org.label-schema.vendor="Voxpupuli" \
      org.label-schema.url="https://github.com/voxpupuli/puppetboard" \
      org.label-schema.license="Apache-2.0" \
      org.label-schema.vcs-url="https://github.com/voxpupuli/puppetboard" \
      org.label-schema.schema-version="1.0" \
      org.label-schema.dockerfile="/Dockerfile"

ENV PUPPETBOARD_PORT=80 \
    PUPPETBOARD_HOST=0.0.0.0 \
    PUPPETBOARD_STATUS_ENDPOINT=/status \
    PUPPETBOARD_SETTINGS=docker_settings.py
EXPOSE 80

HEALTHCHECK --interval=1m --timeout=5s --start-period=10s CMD python3 -c "import requests; import sys; rc = 0 if requests.get('http://localhost:${PUPPETBOARD_PORT}${PUPPETBOARD_URL_PREFIX:-}${PUPPETBOARD_STATUS_ENDPOINT}').ok else 255; sys.exit(rc)"

RUN apk upgrade --no-cache
RUN mkdir -p /usr/src/app/
WORKDIR /usr/src/app/
COPY . /usr/src/app
# The compiled dependencies come as musl wheels and the rest is pure Python,
# so no compiler is needed: keeping gcc, binutils and the -dev packages out of
# the image removes their CVEs. Without gcc a dependency that needs compiling
# fails the build instead of slipping in.
RUN pip install --no-cache-dir --prefer-binary --root-user-action=ignore -r requirements-docker.txt . \
    && pip uninstall -y --root-user-action=ignore pip \
    && rm -rf /usr/local/lib/python3*/ensurepip
# pip is not needed at runtime and ships its own, older urllib3, msgpack and
# setuptools copies that scanners report, so it leaves the image.

COPY Dockerfile /

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# ASGI worker: serves the web UI, the JSON API (ENABLE_API) and the MCP server (ENABLE_MCP)
CMD gunicorn -k asgi -b ${PUPPETBOARD_HOST}:${PUPPETBOARD_PORT} --preload --workers="${PUPPETBOARD_WORKERS:-1}" --root-path="${PUPPETBOARD_URL_PREFIX:-}" --access-logfile=- puppetboard.asgi:app
