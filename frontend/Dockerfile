FROM node:22-alpine
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app
COPY package*.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
RUN pnpm add -g serve

COPY . .

ARG VITE_API_URL
ARG NODE_ENV=production
ENV NODE_ENV=$NODE_ENV

RUN pnpm build

EXPOSE 3000
CMD [ "serve", "-s", "dist" ]
