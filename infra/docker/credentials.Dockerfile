ARG PYTHON_IMAGE=python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
FROM ${PYTHON_IMAGE} AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
COPY packages/credentials/requirements.lock /tmp/requirements.lock
RUN /opt/venv/bin/python -m pip install --require-hashes --only-binary=:all: \
    -r /tmp/requirements.lock

FROM ${PYTHON_IMAGE} AS checks
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/packages/credentials/src" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app
COPY packages/credentials/src /app/packages/credentials/src
COPY tests/credentials /app/tests/credentials
USER 10006:10006
CMD ["python", "-W", "error::ResourceWarning", "-m", "unittest", "discover", "-s", "/app/tests/credentials", "-v"]
