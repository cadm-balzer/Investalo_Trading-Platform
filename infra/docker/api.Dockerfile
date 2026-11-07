ARG PYTHON_IMAGE=python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
FROM ${PYTHON_IMAGE} AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
COPY services/api/requirements.lock /tmp/requirements.lock
RUN /opt/venv/bin/python -m pip install --require-hashes --only-binary=:all: \
    -r /tmp/requirements.lock

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/services/api/src:/app/packages/trading/src" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app
COPY services/api/src /app/services/api/src
COPY packages/trading/src /app/packages/trading/src
USER 10003:10003
CMD ["python", "-m", "uvicorn", "investalo_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--ssl-keyfile", "/run/secrets/api_tls_key", "--ssl-certfile", "/run/secrets/api_tls_cert"]

FROM runtime AS migration
COPY services/api/migrations /app/services/api/migrations
CMD ["python", "-m", "investalo_api.migrate"]

FROM dependencies AS test-dependencies
COPY services/api/requirements-test.lock /tmp/requirements-test.lock
RUN /opt/venv/bin/python -m pip install --require-hashes --only-binary=:all: \
    -r /tmp/requirements-test.lock

FROM migration AS checks
COPY --from=test-dependencies /opt/venv /opt/venv
COPY tests/api /app/tests/api
COPY tests/trading /app/tests/trading
CMD ["python", "-m", "pytest", "/app/tests/api", "-q", "-p", "no:cacheprovider"]
