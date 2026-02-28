FROM node:20-alpine AS builder

WORKDIR /app
COPY apps/lawchat/package*.json ./
RUN npm ci

COPY apps/lawchat .

# FASTAPI_URL is used by Route Handlers at runtime (server-side),
# so it does NOT need to be baked into the build.
RUN npm run build

# ---------------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/.next        ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["npm", "start"]
