# syntax=docker/dockerfile:1

# --- build the static bundle ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- serve it with nginx ---
FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

# --- test: run the frontend unit tests (docker compose --profile test) ---
FROM build AS test
CMD ["npm", "test"]
