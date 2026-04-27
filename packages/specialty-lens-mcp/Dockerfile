# Hugging Face Spaces (Docker SDK) deploy.
# HF Spaces runs the container as UID 1000. The official node:22-alpine image
# already ships with user `node` at UID/GID 1000, so we use that directly
# instead of trying to create a new `user` (which collides with the existing
# group at GID 1000).

FROM node:22-alpine

USER node
ENV HOME=/home/node \
    NODE_ENV=production \
    PORT=7860

WORKDIR $HOME/app

# Install deps as `node` so node_modules is owned correctly
COPY --chown=node:node package.json ./
RUN npm install --omit=dev --no-package-lock --no-audit --no-fund \
    && npm install --no-save --no-package-lock --no-audit --no-fund tsx@4.19.2 typescript@5.7.2

# Sources
COPY --chown=node:node tsconfig.json ./
COPY --chown=node:node src/ ./src/

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://127.0.0.1:7860/healthz || exit 1

CMD ["npx", "tsx", "src/index.ts"]
