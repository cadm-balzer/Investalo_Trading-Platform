ARG NODE_IMAGE=node:24.22.2-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
FROM ${NODE_IMAGE} AS build
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS="--max-old-space-size=768"
COPY apps/cockpit/package.json apps/cockpit/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY apps/cockpit/ ./
RUN npm run build

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=10002:10002 /build/.next/standalone ./
COPY --from=build --chown=10002:10002 /build/.next/static ./.next/static
COPY --from=build --chown=10002:10002 /build/public ./public
USER 10002:10002
CMD ["node", "server.js"]
