ARG UI_SOURCE_DIR=NeMo-Agent-Toolkit-UI

FROM node:18-bullseye-slim AS ui-deps
WORKDIR /src/ui
ARG UI_SOURCE_DIR
COPY ${UI_SOURCE_DIR}/package.json ${UI_SOURCE_DIR}/package-lock.json ./
RUN npm ci

FROM node:18-bullseye-slim AS ui-prod-deps
WORKDIR /src/ui
ARG UI_SOURCE_DIR
COPY ${UI_SOURCE_DIR}/package.json ${UI_SOURCE_DIR}/package-lock.json ./
RUN npm ci --omit=dev

FROM node:18-bullseye-slim AS ui-build
WORKDIR /src/ui
ARG UI_SOURCE_DIR
COPY ${UI_SOURCE_DIR}/ ./
COPY --from=ui-deps /src/ui/node_modules ./node_modules
RUN npm run build

FROM python:3.11-slim AS runtime

# Install Node.js for the UI runtime (proxy + Next server)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG NAT_EXTRAS=most
RUN pip install --no-cache-dir "nvidia-nat[${NAT_EXTRAS}]"

# Copy UI runtime artifacts
COPY --from=ui-build /src/ui/.next/standalone ./
COPY --from=ui-build /src/ui/.next/static ./.next/static
COPY --from=ui-build /src/ui/public ./public
COPY --from=ui-build /src/ui/proxy ./proxy
COPY --from=ui-build /src/ui/constants ./constants
COPY --from=ui-build /src/ui/utils ./utils
COPY --from=ui-prod-deps /src/ui/node_modules ./node_modules

# Copy NAT config and startup script
COPY config.yml /app/config.yml
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV NODE_ENV=production
ENV NAT_BACKEND_URL=http://127.0.0.1:8000
ENV NEXT_INTERNAL_URL=http://127.0.0.1:3099
ENV PORT=3000

CMD ["/app/start.sh"]
