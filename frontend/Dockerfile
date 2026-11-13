# --- build ---
FROM node:24-alpine AS build
RUN corepack enable && corepack prepare pnpm@12.18.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm run build

# --- runtime: adapter-node output is self-contained ---
FROM node:24-alpine
WORKDIR /app
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
ENV NODE_ENV=production PORT=3000
USER node
EXPOSE 3000
CMD ["node", "build"]
