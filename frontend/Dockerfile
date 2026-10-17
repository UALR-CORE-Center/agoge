# Step 1: Build React App
FROM node:23.11-slim AS builder

WORKDIR /frontend
# Dependencies first, so Cloud Build reuses this layer until the lockfile changes.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . ./
# Require setup's generated configuration even when upload ignore rules change.
COPY .env.production ./.env.production

# Create static React files. For more info see package.json
RUN NODE_ENV=production npm run build

# Step 2: Setup NGINX
FROM nginx:alpine

# copy the .conf template
COPY ./.nginx/nginx.conf /etc/nginx/nginx.conf

## Remove default nginx index page and replace it with the static files we created in the first step
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /frontend/dist /usr/share/nginx/html
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
