# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json* ./

# Install dependencies cleanly
RUN npm install

# Copy source code and build production bundle
COPY . .
RUN npm run build

# Production serve stage with Nginx
FROM nginx:alpine

# Remove default site
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA bundle
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom reverse-proxy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
