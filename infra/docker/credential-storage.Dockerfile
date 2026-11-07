ARG PYTHON_IMAGE=python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
FROM ${PYTHON_IMAGE} AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
COPY packages/credentials/requirements.lock /locks/packages/credentials/requirements.lock
COPY services/credentials/requirements.lock services/credentials/requirements-test.lock /locks/services/credentials/
RUN /opt/venv/bin/python -m pip install --require-hashes --only-binary=:all: \
    -r /locks/services/credentials/requirements-test.lock

FROM ${PYTHON_IMAGE} AS checks
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/services/credentials/src:/app/packages/credentials/src:/app/integrations/bitget/src:/app/tests/credential_onboarding" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app
COPY packages/credentials/src /app/packages/credentials/src
COPY services/credentials/src /app/services/credentials/src
COPY integrations/bitget/src /app/integrations/bitget/src
COPY tests/credential_store /app/tests/credential_store
COPY tests/credentials_storage /app/tests/credentials_storage
COPY tests/credential_onboarding /app/tests/credential_onboarding
USER 10003:10003
CMD ["python", "-m", "pytest", "/app/tests/credential_store", "/app/tests/credentials_storage", "/app/tests/credential_onboarding", "-q", "-p", "no:cacheprovider", "--tb=short"]
