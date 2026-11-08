ARG NODE_IMAGE=node:24.22.2-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
FROM ${NODE_IMAGE} AS dependencies
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS="--max-old-space-size=768"
COPY apps/cockpit/package.json apps/cockpit/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

FROM dependencies AS checks
WORKDIR /app/apps/cockpit
ENV NODE_ENV=test
COPY --from=dependencies /build/node_modules /app/node_modules
COPY apps/cockpit/src /app/apps/cockpit/src
COPY tests/infra/passkey_credential_cockpit_driver.ts /app/tests/infra/passkey_credential_cockpit_driver.ts
USER 10003:10003
CMD ["node", "--experimental-strip-types", "/app/tests/infra/passkey_credential_cockpit_driver.ts"]
