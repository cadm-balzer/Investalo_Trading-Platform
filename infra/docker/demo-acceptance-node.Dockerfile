ARG NODE_IMAGE=node:24.22.2-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
FROM ${NODE_IMAGE} AS dependencies
WORKDIR /build
COPY apps/cockpit/package.json apps/cockpit/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app/apps/cockpit
ENV NODE_ENV=test
COPY --from=dependencies /build/node_modules /app/node_modules
COPY apps/cockpit/src /app/apps/cockpit/src
COPY tests/infra/demo_credential_acceptance_driver.ts /app/tests/infra/demo_credential_acceptance_driver.ts
USER 10003:10003
CMD ["node", "--experimental-strip-types", "/app/tests/infra/demo_credential_acceptance_driver.ts"]
