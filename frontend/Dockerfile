FROM node:20-alpine

WORKDIR /app

# pnpm via corepack (versão fixada em package.json > packageManager).
RUN corepack enable

# Instala dependências primeiro (cache de layer).
COPY package.json ./
RUN pnpm install

COPY . .

EXPOSE 5173

# Dev server; sobrescrito pelo docker-compose.
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]
