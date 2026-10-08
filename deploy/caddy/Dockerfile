# Builds the React app and bakes it into Caddy, which serves it with HTTPS.
FROM node:20-alpine AS web
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
# Same origin as the API in production: the browser calls /api/v1 on calaro.online
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

FROM caddy:2.10-alpine
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /app/dist /srv
