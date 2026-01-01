FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/*

# Copy site content and fix permissions
COPY site/ /usr/share/nginx/html/
RUN chmod -R 644 /usr/share/nginx/html/* && \
    find /usr/share/nginx/html -type d -exec chmod 755 {} \;

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
