FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Clean cache and install dependencies
RUN npm cache clean --force && \
    npm install --legacy-peer-deps && \
    npm install ajv@8 --legacy-peer-deps

# Copy source code
COPY . .

# Set environment variable to skip type checking
ENV SKIP_PREFLIGHT_CHECK=true

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built app
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]