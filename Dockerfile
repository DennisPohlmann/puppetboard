# Puppetboard - container image.
#
#   docker build -t puppetboard .
#   docker run -d -p 127.0.0.1:8080:8080 -e PUPPETDB_HOST=puppetdb \
#     -e SECRET_KEY=... puppetboard
#
# Base image (official Python on Alpine) written out in both FROM lines,
# pinned by digest, so Dependabot can update it (a new digest behind the same
# tag is an Alpine or Python patch). All compiled dependencies come as musl
# wheels, so no compiler is installed.
FROM python:3.15-alpine@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore
WORKDIR /src
COPY . .
RUN python -m venv /opt/puppetboard \
 && /opt/puppetboard/bin/pip install --no-cache-dir --prefer-binary -r requirements-docker.txt . \
 && /opt/puppetboard/bin/pip uninstall -y pip

FROM python:3.15-alpine@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd

LABEL org.opencontainers.image.title="puppetboard" \
      org.opencontainers.image.description="Puppetboard - web frontend, read-only JSON API and MCP server for PuppetDB" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/DennisPohlmann/puppetboard"

# Alpine security updates newer than the base image. pip and ensurepip are not
# needed at run time and only add packages (their vendored urllib3, msgpack,
# setuptools copies) to the image scan. Own unprivileged user puppetboard.
RUN apk upgrade --no-cache \
 && python -m pip uninstall -y --root-user-action=ignore pip \
 && rm -rf /usr/local/lib/python3*/ensurepip /root/.cache \
 && addgroup -S -g 10001 puppetboard \
 && adduser -S -D -u 10001 -G puppetboard -h /home/puppetboard -s /sbin/nologin puppetboard

ENV PATH=/opt/puppetboard/bin:$PATH \
    PUPPETBOARD_PORT=8080 \
    PUPPETBOARD_HOST=0.0.0.0 \
    PUPPETBOARD_STATUS_ENDPOINT=/status \
    PUPPETBOARD_SETTINGS=docker_settings.py
COPY --from=build /opt/puppetboard /opt/puppetboard
COPY Dockerfile /

USER puppetboard
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s CMD ["python", "-m", "puppetboard.healthcheck"]

# ASGI worker: serves the web UI, the JSON API (ENABLE_API) and the MCP server
# (ENABLE_MCP). Port, workers and URL prefix come from the environment, see
# puppetboard/gunicorn_conf.py.
ENTRYPOINT ["gunicorn", "-c", "python:puppetboard.gunicorn_conf"]
CMD ["puppetboard.asgi:app"]
